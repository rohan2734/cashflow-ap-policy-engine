# PLAN 2: Core Pipeline Deep Dive

(What each step does + why it exists + how to implement it)

---

# 0. Pipeline Overview

```text id="c3h9xy"
PDF
 ↓
Parser
 ↓
Clause Splitter
 ↓
Cross-Reference Resolver
 ↓
LLM Extraction
 ↓
Validator
 ↓
Rule Builder (AST)
 ↓
Conflict Detector
 ↓
Final Rules (stored)
```

---

# 1. Parser

---

## Why this step exists

```text id="d6t4x1"
PDFs are not structured data.
You must extract text + preserve layout as much as possible.
```

---

## What it does

* reads PDF
* extracts text blocks
* keeps rough structure

---

## Implementation

Use:

* PyMuPDF

```python id="9hx3c6"
import fitz

def parse_pdf(file):
    doc = fitz.open(file)
    blocks = []

    for page in doc:
        blocks.extend(page.get_text("blocks"))

    return blocks
```

---

## Output

```json id="o2u2yf"
[
  {
    "text": "1. Invoice Validation",
    "page": 1
  },
  ...
]
```

---

## Edge Cases Handled

```text id="2n45x4"
- multi-line text
- broken paragraphs
- tables (partial)
```

---

# 2. Clause Splitter

---

## Why this step exists

```text id="e1u8sx"
LLM works best on small, focused chunks.
Policies are long → must split into clauses.
```

---

## What it does

* identifies logical rule units
* assigns clause IDs

---

## Implementation

### Step 1: Regex-based splitting

```python id="2l6p2c"
pattern = r"(\d+(\.\d+)*(\([a-z]\))?)"
```

---

### Step 2: Heuristic fallback

Split by:

```text id="lgd9bp"
- sentences
- keywords: IF, WHEN, SHALL
```

---

## Output

```json id="x4e9fh"
[
  {
    "id": "2.2(c)",
    "text": "Escalate if amount exceeds PO by 10%"
  }
]
```

---

## Edge Cases

```text id="b2lfzn"
- no numbering → fallback splitting
- nested bullets → flatten
- long paragraphs → chunk
```

---

# 3. Cross-Reference Resolver

---

## Why this step exists

```text id="8pnqyr"
Rules are often incomplete without references:
"Refer Section 2.3(b)"
```

---

## What it does

* detects references
* links clauses
* merges context

---

## Implementation

---

### Step 1: Extract references

```python id="qf3n0g"
import re

refs = re.findall(r"Section\s+(\d+(\.\d+)*(\([a-z]\))?)", text)
```

---

### Step 2: Build graph

```python id="3n7h0l"
graph = {
  "2.2(c)": ["2.3(b)"]
}
```

---

### Step 3: Resolve via DFS

```python id="7i8k2d"
def resolve(clause_id, visited):
    if clause_id in visited:
        return []

    visited.add(clause_id)

    result = [clause_map[clause_id]]

    for ref in graph[clause_id]:
        result += resolve(ref, visited)

    return result
```

---

## Output

```text id="k7z8sp"
Merged clause with referenced definitions
```

---

## Edge Cases

```text id="7n7c3k"
- circular references
- missing references
- partial references
```

---

# 4. LLM Extraction

---

## Why this step exists

```text id="l3o4i7"
Convert natural language → structured rule
```

---

## What it does

Extract:

* condition (AST-like)
* action
* exceptions

---

## Implementation

---

### Prompt

```text id="7nl9bi"
Extract:
- condition (structured JSON)
- action (ENUM)
- exceptions

Return ONLY valid JSON.
```

---

### Call (async)

```python id="5o7k1t"
async def extract_clause(clause):
    return await llm.generate(prompt + clause["text"])
```

---

## Output

```json id="1m1o3c"
{
  "condition": {
    "field": "invoice_total",
    "op": ">",
    "value": "po_amount * 1.1"
  },
  "action": "ESCALATE"
}
```

---

## Edge Cases

```text id="s3k6v7"
- ambiguous wording
- missing action
- multiple conditions
```

---

# 5. Validator

---

## Why this step exists

```text id="c5n3fd"
LLM output is unreliable → must enforce correctness
```

---

## What it checks

---

### 1. Structure

```python id="9p3k7f"
if "condition" not in rule:
    fail
```

---

### 2. Schema

```text id="r4o2fy"
valid operators: >, <, >=
```

---

### 3. Variables

```text id="q5z6ye"
invoice_total exists?
po_amount exists?
```

---

### 4. Expression validity

* AST must be evaluatable

---

## Output

```text id="k8m2fd"
valid / invalid
```

---

## Action on failure

```text id="2l7yhg"
retry with smaller prompt
or mark low confidence
```

---

# 6. Rule Builder (AST)

---

## Why this step exists

```text id="c2k4tp"
String conditions are not executable
AST makes rules deterministic
```

---

## What it does

Convert:

```text id="s1x2zy"
"invoice > po * 1.1"
```

Into:

```json id="n9m4zv"
{
  "op": ">",
  "left": "invoice_total",
  "right": {
    "op": "*",
    "left": "po_amount",
    "right": 1.1
  }
}
```

---

## Output

Executable rule

---

## Edge Cases

```text id="q9l7sk"
- nested conditions
- AND/OR logic
```

---

# 7. Conflict Detector

---

## Why this step exists

```text id="j4k2sa"
Policies may contain conflicting rules
```

---

## What it does

Detect:

```text id="m3n6ko"
overlapping conditions + different actions
```

---

## Implementation

---

### Normalize rules

```text id="f6z2xd"
convert conditions → intervals + predicates
```

---

### Check overlap

```python id="b7l3pz"
if interval_overlap(rule1, rule2):
    if rule1.action != rule2.action:
        conflict = True
```

---

## Output

```json id="k9z7xp"
{
  "conflicts": [...]
}
```

---

## Edge Cases

```text id="t7y2pl"
- partial overlap
- exception overrides
```

---

# 8. Final Output

---

## Stored Rule

```json id="c5z9yt"
{
  "rule_id": "AP-001",
  "condition": {...},
  "action": "ESCALATE",
  "confidence": 0.82,
  "source_clauses": ["2.2(c)", "2.3(b)"]
}
```

---

# 9. Key Design Strengths

---

## Determinism

```text id="q1m5px"
All rules are executable without LLM
```

---

## Traceability

```text id="j7k3sd"
rule → clause → document
```

---

## Modularity

```text id="y4l2op"
each step is replaceable
```

---

## Robustness

```text id="t6p8wr"
validation prevents bad rules
```

---

# 10. What You Say in Interview

```text id="z9n6kx"
“I designed the pipeline like a compiler:
parse → transform → validate → execute

LLM is only used for semantic parsing,
everything else is deterministic.”
```

---