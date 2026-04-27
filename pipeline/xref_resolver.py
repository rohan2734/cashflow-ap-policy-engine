import re

from shared_types.pipeline import Clause, EnrichedClause, ReferencedClause


_XREF = re.compile(r"(?:Section|Clause|Refer)\s+(\d+(\.\d+)*(\([a-z]\))?)", re.IGNORECASE)


class CircularReferenceError(Exception):
    pass


def resolve_references(clauses: list[Clause]) -> list[EnrichedClause]:
    clause_map = {c.id: c for c in clauses}
    graph = {
        c.id: [m.group(1) for m in _XREF.finditer(c.text) if m.group(1) != c.id]
        for c in clauses
    }
    return [
        EnrichedClause(
            id=c.id,
            text=c.text,
            page=c.page,
            referenced_clauses=_dfs(c.id, graph, clause_map, frozenset()),
        )
        for c in clauses
    ]


def _dfs(
    cid: str,
    graph: dict[str, list[str]],
    clause_map: dict[str, Clause],
    visited: frozenset[str],
) -> list[ReferencedClause]:
    if cid in visited:
        raise CircularReferenceError(f"Circular reference at {cid!r}")
    visited = visited | {cid}
    result: list[ReferencedClause] = []
    for ref in graph.get(cid, []):
        if ref in clause_map:
            result.append(ReferencedClause(id=ref, text=clause_map[ref].text))
            result.extend(_dfs(ref, graph, clause_map, visited))
    return result
