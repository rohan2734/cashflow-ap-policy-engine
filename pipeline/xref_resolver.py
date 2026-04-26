import re
from shared_types.pipeline import Clause, EnrichedClause


XREF = re.compile(r"(?:Section|Clause|Refer)\s+(\d+(\.\d+)*(\([a-z]\))?)", re.IGNORECASE)


class CircularReferenceError(Exception):
    pass


def resolve_references(clauses: list[Clause]) -> list[EnrichedClause]:
    clause_map = {c.id: c for c in clauses}
    graph = {c.id: [m.group(1) for m in XREF.finditer(c.text) if m.group(1) != c.id]
             for c in clauses}
    return [
        EnrichedClause(
            id=c.id, text=c.text, page=c.page,
            referenced_texts=_dfs(c.id, graph, clause_map, frozenset()),
        )
        for c in clauses
    ]


def _dfs(cid: str, graph: dict, clause_map: dict, visited: frozenset) -> list[str]:
    if cid in visited:
        raise CircularReferenceError(f"Circular reference at {cid}")
    visited = visited | {cid}
    texts: list[str] = []
    for ref in graph.get(cid, []):
        if ref in clause_map:
            texts.append(clause_map[ref].text)
            texts.extend(_dfs(ref, graph, clause_map, visited))
    return texts
