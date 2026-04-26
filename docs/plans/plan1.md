# PLAN 1: High-Level Overview + Setup (Refined)

# 1. What We Are Building

```text
A config-driven system that:
- Converts policy PDFs → deterministic rules (AST)
- Executes rules on invoice JSON
- Generates decisions + notifications
- Provides visualization + observability
- Uses external LLMs (NVIDIA / Bedrock) via abstraction
```

---

# 2. Core Design Principles

```text
1. LLM is used ONLY for semantic extraction
2. All execution is deterministic (no LLM in runtime decisions)
3. System is modular and replaceable
4. LLM provider is configurable (NVIDIA / Bedrock / fallback)
5. Fully observable (Langfuse tracing)
6. No unnecessary infra (no queue, no workers)
```

---

# 3. High-Level Architecture

```text
                ┌──────────────────────┐
                │         UI           │
                │ (Config + Upload)    │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │      FastAPI         │
                │   (Single Service)   │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │    Orchestrator      │
                └──────────┬───────────┘
                           ↓
        ┌────────────────────────────────────┐
        │           Pipeline                 │
        │ Parser → Splitter → XRef → LLM     │
        │ → Validator → Rule Builder         │
        └────────────────────────────────────┘
                           ↓
                ┌──────────────────────┐
                │     Postgres DB      │
                │ (rules + config)     │
                └──────────┬───────────┘
                           ↓
        ┌────────────────────────────────────┐
        │ Runtime Layer                      │
        │ - Execution Engine                 │
        │ - Notification Service             │
        │ - Visualization (Graph)            │
        └────────────────────────────────────┘
                           ↓
                ┌──────────────────────┐
                │     Langfuse         │
                │   (Observability)    │
                └──────────────────────┘
```

---

# 4. Key Simplifications (Intentional)

```text
- No Redis queue → use async processing
- No worker services → pipeline runs inside API
- No Triton → FastAPI is enough
- No GPU infra → use NVIDIA / Bedrock APIs
```

---

# 5. LLM Strategy

---

## 5.1 Supported Providers

```text
- NVIDIA DeepSeek endpoint
- AWS Bedrock (Claude / others)
```

---

## 5.2 LLM Abstraction Layer

```python
class LLMClient:

    async def generate(self, prompt):
        if self.provider == "nvidia":
            return await self._nvidia_call(prompt)
        elif self.provider == "bedrock":
            return await self._bedrock_call(prompt)
```

---

## 5.3 Config Example

```json
{
  "llm": {
    "provider": "nvidia",
    "model": "deepseek-ai/deepseek-v3",
    "temperature": 0.1,
    "max_tokens": 400
  },
  "concurrency": {
    "max_parallel_clauses": 10
  }
}
```

---

# 6. Concurrency Model (No Queue)

---

## Use Async + Semaphore

```python
import asyncio

semaphore = asyncio.Semaphore(10)

async def process_clause(clause):
    async with semaphore:
        return await llm.generate(clause)
```

---

## Parallel Execution

```python
tasks = [process_clause(c) for c in clauses]
results = await asyncio.gather(*tasks)
```

---

## Why this works

```text
- avoids rate limit bursts
- keeps system simple
- easy to debug
```

---

# 7. Rate Limiting Strategy

---

## Basic Control

```python
semaphore = asyncio.Semaphore(10)
```

---

## Add Delay (optional)

```python
await asyncio.sleep(0.1)
```

---

## Retry

```python
for attempt in range(2):
    try:
        return await llm_call()
    except:
        await asyncio.sleep(2 ** attempt)
```

---

# 8. Setup Plan

---

## Step 1: Project Structure

```text
/project
  /api
  /pipeline
  /engine
  /llm
  /config
  /db
  /notifications
  /visualization
  docker-compose.yml
```

---

## Step 2: Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy asyncpg pymupdf langfuse
```

---

## Step 3: Start Services

```bash
docker-compose up
```

Runs:

* Postgres
* Langfuse

(FastAPI runs locally)

---

## Step 4: Configure LLM

Set:

```json
{
  "provider": "nvidia"
}
```

OR

```json
{
  "provider": "bedrock"
}
```

---

## Step 5: Upload Document

```http
POST /upload
```

---

## Step 6: Pipeline Runs

```text
Upload → Parse → Extract → Validate → Store Rules
```

---

## Step 7: Fetch Rules

```http
GET /rules/{doc_id}
```

---

## Step 8: Execute Rules

```http
POST /execute
```

---

## Step 9: Monitor via Langfuse

Track:

* prompts
* outputs
* latency
* retries

---

# 9. Expected Performance

---

## Per Document

```text
~100 clauses
~120 LLM calls
parallel (10 at a time)

Total time: ~10–20 seconds
```

---

# 10. Deployment Modes

---

## Mode 1: Demo (recommended)

```text
- NVIDIA endpoint
- FastAPI
- async processing
```

---

## Mode 2: Enterprise

```text
- Bedrock
- stricter rate limits
- audit logging
```

---

# 11. What You Should Explicitly Mention

```text
- System is config-driven (LLM + prompts)
- No over-engineering (no queue needed for current scale)
- Async concurrency handles performance
- LLM is replaceable via abstraction layer
- Deterministic validation ensures correctness
- Observability enables debugging
```
