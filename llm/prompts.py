EXTRACTION_PROMPT = """\
Extract a structured rule from the policy clause below.

Return ONLY valid JSON:
{{
  "condition": {{"op": "<op>", "left": "<field or node>", "right": "<value or node>"}},
  "action": "APPROVE | ESCALATE | REJECT",
  "exceptions": ["..."]
}}

Valid ops: >, <, >=, <=, ==, AND, OR, NOT, *, +

Clause:
{clause_text}
"""

RETRY_EXTRACTION_PROMPT = """\
Previous extraction failed validation. Extract only the core rule.

Return ONLY valid JSON with "condition", "action", "exceptions".

Clause:
{clause_text}
"""