import re

from shared_types.pipeline import RawBlock, Clause


_NUMBERED = re.compile(r"^(\d+(\.\d+)*(\([a-z]\))?)\s")


def split_into_clauses(blocks: list[RawBlock]) -> list[Clause]:
    clauses: list[Clause] = []
    for block in blocks:
        clause_id = _numbered_id(block.text)
        for idx, sent in enumerate(_sentences(block.text)):
            if clause_id:
                cid = clause_id if idx == 0 else f"{clause_id}-s{idx}"
            else:
                cid = f"p{block.page}-s{idx}"
            clauses.append(Clause(id=cid, text=sent, page=block.page))
    return clauses


def _numbered_id(text: str) -> str | None:
    m = _NUMBERED.match(text)
    return m.group(1) if m else None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
