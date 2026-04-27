# Pipeline Documentation

## Overview

The CashFlo policy processing pipeline converts PDF policy documents into structured, executable business rules. This document explains the complete pipeline flow and LLM call patterns.

## Pipeline Stages

### 1. PDF Parsing (`parse_pdf`)
**Purpose**: Extract raw text blocks from PDF document  
**LLM Calls**: 0  
**Input**: PDF file path  
**Output**: List of `RawBlock` objects (text + page number)

**Process**:
- Reads PDF file using PyPDF2
- Extracts text content page by page
- Splits content into logical blocks based on formatting
- Returns structured blocks with page references

---

### 2. Normative Classification (`classify_normative_blocks`)
**Purpose**: Identify which blocks contain actual policy rules vs. headings/definitions  
**LLM Calls**: 1 (batch processing)  
**Input**: List of all `RawBlock` objects  
**Output**: Filtered list of normative blocks

**Process**:
- Automatically includes numbered blocks (e.g., "1.2.3(a)") as normative
- Sends all blocks to LLM with classification prompt
- LLM returns indices of blocks containing normative language
- Combines numbered blocks + LLM-selected blocks
- **LLM Prompt**: `CLASSIFY_PROMPT` - identifies obligations, conditions, permissions, prohibitions

**Why 1 LLM call**: All blocks are processed in a single batch request for efficiency.

---

### 3. Clause Splitting (`split_into_clauses`)
**Purpose**: Split normative blocks into individual policy clauses  
**LLM Calls**: 0  
**Input**: Normative blocks  
**Output**: List of `Clause` objects

**Process**:
- Splits blocks at sentence boundaries
- Identifies individual policy statements
- Creates clause objects with unique IDs
- Preserves page number references

---

### 4. Reference Resolution (`resolve_references`)
**Purpose**: Build cross-reference graph between clauses  
**LLM Calls**: 0  
**Input**: List of `Clause` objects  
**Output**: List of `EnrichedClause` objects with references

**Process**:
- Scans clause text for references (e.g., "Section 3.2", "Clause 1.1(a)")
- Builds directed graph of clause relationships
- Performs DFS to collect transitive references
- Detects circular references (raises error)
- Enriches each clause with its referenced clauses

---

### 5. Rule Extraction (`extract_clause`)
**Purpose**: Extract structured rule from each clause  
**LLM Calls**: N (one per clause) + potential retries  
**Input**: `EnrichedClause` object  
**Output**: `RuleRecord` or `None` (if failed)

**Process**:
- For each clause, sends extraction prompt to LLM
- LLM returns structured JSON with condition, action, exceptions, confidence
- Validates extraction against schema and allowed values
- If validation fails, retries with error-specific prompt
- **LLM Prompt**: `EXTRACTION_PROMPT` - extracts condition AST, action, exceptions
- **Retry Prompt**: `RETRY_EXTRACTION_PROMPT` - fixes validation errors

**Parallel Processing**: Uses semaphore to limit concurrent extractions (configurable via `max_parallel_clauses`).

**Why N LLM calls**: Each clause requires individual extraction because:
- Clauses have different contexts and conditions
- Extraction requires understanding of specific clause semantics
- Parallel processing improves throughput

**Retry Logic**:
- First attempt: Standard extraction
- If validation fails: Retry with error context
- Retry confidence capped at 0.5 (penalizes failed first attempt)
- Max 2 attempts per clause

---

### 6. Conflict Detection (`detect_conflicts`)
**Purpose**: Identify conflicting rules that could cause ambiguous decisions  
**LLM Calls**: M (for logical conflicts only)  
**Input**: List of `RuleRecord` objects  
**Output**: List of `ConflictReport` objects

**Process**:

#### A. Numeric Conflict Detection (`detect_numeric_conflicts`)
**LLM Calls**: 0  
**Method**: Algorithmic interval overlap detection

**Process**:
- Identifies simple numeric conditions (e.g., `invoice_amount > 10000`)
- Groups rules by field (e.g., all rules checking `invoice_amount`)
- Converts conditions to intervals (e.g., `> 10000` → `(10000, ∞)`)
- Detects overlapping intervals with different actions
- **No LLM needed**: Pure mathematical analysis

#### B. Logical Conflict Detection (`detect_logical_conflicts`)
**LLM Calls**: M (one per conflicting pair)  
**Method**: LLM-based semantic analysis

**Process**:
- Identifies compound conditions (AND/OR/NOT)
- For each pair with different actions and shared fields:
  - Sends both rules to LLM for conflict analysis
  - LLM determines if conditions can both be satisfied
  - Returns conflict reason if found
- **LLM Prompt**: `CONFLICT_CHECK_PROMPT` - semantic conflict detection

**Why M LLM calls**: Only checks pairs that:
- Have different actions (APPROVE vs REJECT)
- Share at least one field
- Have compound conditions (complex logic)

**Optimization**: Skips pairs with same action or no shared fields.

---

### 7. Persistence (`persist`)
**Purpose**: Store rules and conflicts in database  
**LLM Calls**: 0  
**Input**: `RuleRecord` list, `ConflictReport` list  
**Output**: Database records

**Process**:
- Determines status based on confidence threshold
  - `confidence >= threshold`: `auto_approved`
  - `confidence < threshold`: `pending_review`
- Inserts rules with appropriate status
- Inserts conflicts with document reference
- Commits transaction

---

## LLM Call Summary

### Base LLM Calls (per document)

| Stage | Calls | Purpose | Parallel |
|-------|-------|---------|----------|
| Classification | 1 | Identify normative blocks | No |
| Extraction | N | Extract rules from clauses | Yes |
| Conflict Detection | M | Detect logical conflicts | Yes |

**Total Base Calls**: `1 + N + M`

### Retry LLM Calls (conditional)

| Scenario | Additional Calls | Trigger |
|----------|------------------|---------|
| Extraction validation failure | +1 per failed clause | Invalid action/condition/ops |
| JSON parsing failure | +1 per failed clause | Malformed LLM response |

**Worst Case**: `1 + 2N + M` (if every extraction fails once)

### Typical Document Analysis

For a typical policy document:
- **Blocks**: 50-100
- **Normative blocks**: 10-20
- **Clauses**: 8-15
- **Compound rules**: 2-5
- **Conflict pairs**: 1-3

**Typical LLM calls**: `1 + 12 + 2 = 15` calls
**Worst case**: `1 + 24 + 2 = 27` calls

---

## Why You See 3-4 "extract_clause_success" Messages

The logs show multiple "extract_clause_success" messages because:

1. **Multiple Clauses**: Your document contained 3-4 normative clauses
2. **Parallel Processing**: All extractions happen concurrently
3. **Individual Success**: Each clause extraction is logged separately

**Example Log Flow**:
```
pipeline_start
├── parse_pdf_complete (50 blocks)
├── classify_complete (12 normative blocks) ← 1 LLM call
├── split_complete (8 clauses)
├── resolve_complete (8 enriched clauses)
├── extract_start (8 clauses)
│   ├── extract_clause_success (clause_1) ← 1 LLM call
│   ├── extract_clause_success (clause_2) ← 1 LLM call
│   ├── extract_clause_success (clause_3) ← 1 LLM call
│   ├── extract_clause_success (clause_4) ← 1 LLM call
│   └── ... (4 more clauses)
├── conflict_complete (2 conflicts) ← 2 LLM calls
└── pipeline_complete
```

**Total LLM calls**: `1 (classification) + 8 (extraction) + 2 (conflicts) = 11`

---

## Performance Optimization

### Current Optimizations

1. **Batch Classification**: All blocks classified in single LLM call
2. **Parallel Extraction**: Multiple clauses processed concurrently
3. **Selective Conflict Detection**: Only checks relevant rule pairs
4. **Algorithmic Numeric Conflicts**: No LLM needed for simple numeric overlaps

### Potential Optimizations

1. **Batch Extraction**: Send multiple clauses to LLM in single request
2. **Cached Classification**: Reuse classification for similar documents
3. **Early Termination**: Stop conflict detection after finding N conflicts
4. **Semantic Caching**: Cache extraction results for similar clauses

---

## Error Handling

### Extraction Failures

**Causes**:
- Invalid action (not in APPROVE/ESCALATE/REJECT)
- Invalid operator (not in >, <, >=, <=, ==, AND, OR, NOT)
- Missing condition
- Malformed JSON response

**Handling**:
- Automatic retry with error context
- Confidence penalty on retry (max 0.5)
- Clause skipped if retry fails
- Logged with full error details

### Conflict Detection Failures

**Causes**:
- LLM timeout
- JSON parsing error
- Network issues

**Handling**:
- Logged as warning
- Conflict pair skipped
- Pipeline continues with other conflicts

---

## Configuration

### Key Configuration Parameters

```python
# Concurrency
max_parallel_clauses: int  # Max concurrent extractions (default: 5)

# Quality Control
confidence_threshold: float  # Auto-approve threshold (default: 0.8)

# LLM Settings
provider: str  # nvidia | openrouter | bedrock
model: str  # Model identifier
temperature: float  # LLM temperature (default: 0.1)
max_tokens: int  # Max tokens per response (default: 2000)
```

### Cost Estimation

**Per Document Cost**:
- Classification: ~1,000 tokens
- Extraction: ~500 tokens per clause
- Conflict Detection: ~300 tokens per pair

**Example** (8 clauses, 2 conflicts):
- Input: `1,000 + (8 × 500) + (2 × 300) = 5,600` tokens
- Output: `200 + (8 × 300) + (2 × 100) = 2,800` tokens
- **Total**: ~8,400 tokens per document

---

## Monitoring & Observability

### Key Metrics

- **Pipeline Duration**: Total processing time
- **LLM Call Count**: Number of LLM requests
- **Extraction Success Rate**: Successful extractions / total clauses
- **Conflict Detection Rate**: Conflicts found / total rule pairs
- **Auto-approval Rate**: Auto-approved rules / total rules

### Logging

**Info Level**:
- Pipeline stage completion
- LLM call success/failure
- Extraction results with previews
- Conflict detection results

**Debug Level**:
- Individual clause processing
- LLM request/response details
- Validation steps

**Warning Level**:
- Extraction retries
- Conflict detection failures
- Validation errors

---

## Future Enhancements

1. **Incremental Processing**: Process only changed clauses
2. **Rule Versioning**: Track rule evolution over time
3. **Impact Analysis**: Predict effects of rule changes
4. **Natural Language Explanations**: Generate human-readable rule descriptions
5. **Test Case Generation**: Create test scenarios from rules
6. **Rule Optimization**: Suggest rule simplifications