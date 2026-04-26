import re
from shared_types.pipeline import RawBlock, Clause


NUMBERED = re.compile(r"^(\d+(\.\d+)*(\([a-z]\))?)\s")
KEYWORDS = re.compile(r"\b(IF|WHEN|SHALL|MUST|UNLESS|EXCEPT)\b")


def split_into_clauses(blocks: list[RawBlock]) -> list[Clause]:
    clauses: list[Clause] = []
    for block in blocks:
        clause_id = _numbered_id(block.text)
        if clause_id:
            clauses.append(Clause(id=clause_id, text=block.text, page=block.page))
        elif KEYWORDS.search(block.text):
            for idx, sent in enumerate(_sentences(block.text)):
                clauses.append(Clause(id=f"p{block.page}-s{idx}", text=sent, page=block.page))
    return clauses


def _numbered_id(text: str) -> str | None:
    m = NUMBERED.match(text)
    return m.group(1) if m else None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
