Great, now let’s finish strong.

---

# PLAN 3: Bonus Features

(What to add + why it matters + exactly how to implement)

These are the things that **differentiate you from 90% of submissions**.

---

# 0. Bonus Features Overview

```text id="8q7f1m"
1. Rule Execution Engine
2. Email Notifications on Deviations
3. Visual Rule Graph
4. Confidence Scoring + Human Review
5. Multi-Document Support
6. (Optional) Prompt Versioning + Experimentation
```

---

# 1. Rule Execution Engine

---

## Why this matters

```text id="s1kp2m"
Most people stop at extraction.
Execution proves your rules are actually usable.
```

---

## What it does

Input:

```json id="6n9v0q"
invoice.json + rules.json
```

Output:

```json id="k4q8dx"
{
  "decision": "ESCALATE",
  "triggered_rules": [...],
  "reasons": [...]
}
```

---

## Implementation

---

### Step 1: AST Evaluator

```python id="5c3n9k"
def eval_condition(node, context):
    if node["op"] == "AND":
        return all(eval_condition(n, context) for n in node["operands"])

    if node["op"] == ">":
        return resolve(node["left"], context) > resolve(node["right"], context)
```

---

### Step 2: Execute Rules

```python id="9t2k1z"
def execute_rules(rules, invoice):
    triggered = []

    for rule in rules:
        if eval_condition(rule["condition"], invoice):
            triggered.append(rule)

    return triggered
```

---

### Step 3: Final Decision

```python id="3l8f2c"
priority = {
    "REJECT": 3,
    "ESCALATE": 2,
    "APPROVE": 1
}

decision = max(triggered, key=lambda r: priority[r["action"]])
```

---

## What to highlight

```text id="4n8k6x"
- No LLM used in execution
- Fully deterministic
- Debuggable
```

---

# 2. Email Notifications on Deviations

---

## Why this matters

```text id="6h2k9m"
Shows real-world integration capability
```

---

## When to trigger

Inside execution:

```python id="7k2p9c"
if rule["action"] == "ESCALATE":
    send_notification(rule, invoice)
```

---

## Email Content

```text id="1z8k3m"
Invoice Number
Vendor Name
Deviation Type
Recommended Action
```

---

## Implementation

---

### Step 1: Build Message

```python id="2m7k1q"
def build_email(rule, invoice):
    return f"""
    Invoice: {invoice['id']}
    Vendor: {invoice['vendor']}
    Issue: {rule['description']}
    Action: {rule['action']}
    """
```

---

### Step 2: Send Email

Use SMTP:

```python id="9p3k1f"
import smtplib
```

---

## Better (optional)

```text id="3q9k2p"
Execution → background thread → email send
```

---

# 3. Visual Rule Graph

---

## Why this matters

```text id="2k8f7m"
Makes your system explainable
```

---

## What it shows

* decision flow
* rule branching

---

## Implementation

Use:

* Graphviz

---

### Example

```python id="4t8k1m"
from graphviz import Digraph

dot = Digraph()

dot.node("A", "Check Amount")
dot.node("B", "Auto Approve")
dot.node("C", "Escalate")

dot.edge("A", "B", "<1L")
dot.edge("A", "C", ">10%")

dot.render("rules")
```

---

## Advanced (optional)

* generate graph from AST automatically

---

# 4. Confidence Scoring + Human Review

---

## Why this matters

```text id="7p1k3n"
LLM is probabilistic → you must handle uncertainty
```

---

## Confidence Formula

```python id="9c4k2m"
confidence =
    0.5 * validation_score +
    0.3 * retry_penalty +
    0.2 * structure_score
```

---

## Signals

---

### 1. Validation success

* full pass → high score

---

### 2. Retry count

* more retries → lower confidence

---

### 3. Missing fields

* penalize

---

## Output

```json id="3m8k2q"
{
  "rule_id": "AP-001",
  "confidence": 0.58,
  "needs_review": true
}
```

---

## Human Review Flow

```text id="6k2p9f"
low confidence → UI → user edits rule → save
```

---

# 5. Multi-Document Support

---

## Why this matters

```text id="4p7k1m"
Shows generalization beyond one document
```

---

## Problem

Different domains:

* AP
* HR
* Procurement

---

## Solution

---

### 1. Domain Config

```json id="2k8p1m"
{
  "domain": "AP",
  "fields": ["invoice_total", "po_amount"]
}
```

---

### 2. Prompt Variation

```text id="9m2k1p"
AP → invoices
HR → reimbursements
```

---

### 3. Rule Namespacing

```json id="3p7k1m"
{
  "domain": "AP",
  "rule_id": "AP-001"
}
```

---

## Pipeline stays same

```text id="8k1p2m"
only config changes
```

---

# 6. Prompt Versioning (Underrated but powerful)

---

## Why this matters

```text id="7k2p1m"
LLM quality depends heavily on prompts
```

---

## Implementation

Use:

* Langfuse

---

### Store prompts

```text id="2p8k1m"
rule_extraction_v1
rule_extraction_v2
```

---

### Fetch dynamically

```python id="9k2p1m"
prompt = langfuse.get_prompt("rule_extraction_v2")
```

---

## Benefit

```text id="3k7p1m"
- easy experimentation
- no code changes
```

---

# 7. What Makes Your Solution Stand Out

---

## You didn’t just extract rules

You built:

```text id="5k2p1m"
- execution engine
- notification system
- visualization layer
- human-in-loop review
```

---

## You controlled LLM usage

```text id="7p3k1m"
LLM → only extraction
everything else → deterministic
```

---

## You handled real-world complexity

```text id="9k1p2m"
- conflicts
- cross references
- ambiguity
```

---

# 8. What to Say in Interview

```text id="2k9p1m"
“I extended the system beyond extraction by building an execution engine,
notification layer, and confidence-based human review.

This ensures the system is not just accurate, but also usable in production.”
```

---

# Final Wrap-Up

---

You now have:

```text id="4k2p1m"
Plan 1 → architecture + setup
Plan 2 → core pipeline (deep logic)
Plan 3 → bonus features (differentiation)
```
