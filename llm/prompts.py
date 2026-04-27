EXTRACTION_PROMPT = """\
Extract a structured policy rule from the clause below.

Known fields — use these exact names:
  invoice_amount      numeric  total invoice value
  invoice_age_days    numeric  days since invoice date
  vendor_status       string   "approved" | "suspended" | "probationary"
  vendor_tier         string   "preferred" | "standard" | "new"
  payment_terms_days  numeric  agreed payment window in days
  expense_category    string   "capex" | "opex" | "travel" | "services"
  approval_level      string   "manager" | "director" | "vp" | "cfo"
  contract_status     string   "active" | "expired" | "pending"
  po_matched          boolean  true | false

Valid ops: >, <, >=, <=, ==, AND, OR, NOT

For unconditional obligations ("vendor must provide X"), express the violation
condition as the rule (e.g. po_matched == false → REJECT).

Return ONLY valid JSON:
{{
  "condition": {{"op": "<op>", "left": "<field or node>", "right": "<value or node>"}},
  "action": "APPROVE | ESCALATE | REJECT",
  "exceptions": ["<exception text>", "..."],
  "confidence": <float 0.0–1.0 — your certainty this extraction is correct>
}}

Score confidence lower when: clause is ambiguous, action is not explicit,
field mapping required inference, or condition structure is uncertain.

--- EXAMPLES ---

Clause: "Invoices above $10,000 require director-level approval."
{{
  "condition": {{"op": ">", "left": "invoice_amount", "right": 10000}},
  "action": "ESCALATE",
  "exceptions": [],
  "confidence": 0.95
}}

Clause: "Reject all invoices from suspended vendors regardless of amount."
{{
  "condition": {{"op": "==", "left": "vendor_status", "right": "suspended"}},
  "action": "REJECT",
  "exceptions": [],
  "confidence": 0.98
}}

Clause: "Approve invoices under $500 from preferred vendors with active contracts."
{{
  "condition": {{
    "op": "AND",
    "left": {{"op": "<", "left": "invoice_amount", "right": 500}},
    "right": {{
      "op": "AND",
      "left": {{"op": "==", "left": "vendor_tier", "right": "preferred"}},
      "right": {{"op": "==", "left": "contract_status", "right": "active"}}
    }}
  }},
  "action": "APPROVE",
  "exceptions": ["emergency_procurement"],
  "confidence": 0.91
}}

Clause: "All vendor invoices must include a valid PO number."
{{
  "condition": {{"op": "==", "left": "po_matched", "right": false}},
  "action": "REJECT",
  "exceptions": [],
  "confidence": 0.80
}}

--- END EXAMPLES ---

Clause:
{clause_text}
"""

RETRY_EXTRACTION_PROMPT = """\
The previous extraction failed validation. Re-extract the rule, fixing the specific error below.

Error: {error}

What was previously extracted:
  action:    {previous_action}
  condition: {previous_condition}

Valid actions: {valid_actions}
Valid ops:     {valid_ops}

Return ONLY valid JSON with "condition", "action", "exceptions", "confidence".

Clause:
{clause_text}
"""

CLASSIFY_PROMPT = """\
You are a policy analyst. Review the text blocks below from a policy document.
Return the 0-based indices of blocks that contain normative policy language:
obligations (must, shall, will, required, is responsible for),
conditions (if, when, unless, provided that),
permissions (may, is permitted to),
prohibitions (must not, shall not, prohibited, not allowed),
or penalties (will be rejected, incurs, subject to).

Exclude: section headings, table of contents entries, pure definitions,
page numbers, pure cross-references with no obligation.

Blocks:
{blocks}

Return ONLY valid JSON: {{"normative_indices": [0, 2, 5, ...]}}
"""

CONFLICT_CHECK_PROMPT = """\
Two policy rules are shown below. Determine if they conflict.

Rules conflict when their conditions can BOTH be satisfied at the same time
AND they prescribe different actions.

Rule 1 (action: {action1}):
  condition: {condition1}

Rule 2 (action: {action2}):
  condition: {condition2}

Return ONLY valid JSON:
{{"conflicts": true, "reason": "<brief explanation>"}}
or
{{"conflicts": false, "reason": ""}}
"""
