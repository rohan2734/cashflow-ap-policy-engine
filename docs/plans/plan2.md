# Plan 2: Implementation Guide — Phases 1-9

## Current State (2026-04-26)

Phase 0 complete. All business modules are empty `__init__.py` stubs.

```
DONE   Dockerfile, docker-compose.yml, docker-compose.prod.yml
DONE   infra/nginx/nginx.conf
DONE   .env.example, config.json, requirements.txt
DONE   db/init.sql
STUB   shared_types/, config/, db/, llm/, pipeline/, engine/, notifications/, visualization/, api/
STUB   main.py  (health route only)
STUB   ui/src/app/page.tsx  (placeholder only)
```

Default config is seeded into the DB on first boot — `config.json` is removed.
Seeder inserts default rows into `llm_providers`, `prompts`, and `pipelines` if tables are empty.

---

## Implementation Sequence

```
Phase 1   shared_types  →  config  →  db
Phase 2   llm/prompts   →  llm/client
Phase 3   pipeline steps (parser through conflict_detector)
Phase 4   pipeline/orchestrator
Phase 5   engine/evaluator  →  engine/executor
Phase 6   notifications/dispatcher  →  visualization/graph_builder
Phase 7   api/schemas  →  api/dependencies  →  api/routes  →  main.py update
Phase 8   UI
Phase 9   production hardening
```

No circular imports. Each phase depends only on phases above it.

---

## Entity Relationship Diagram

```
llm_providers
  provider_id  PK
  name
  type                        ◄─────────────────────────────────┐
  config JSONB                                                   │ FK: llm_provider_id
  active BOOL                                                    │
                                                                 │
prompts                                                    pipelines
  prompt_id    PK                                            pipeline_id   PK
  name                  ◄────── FK: prompt_id ──────────    name
  version                                                    llm_provider_id  FK → llm_providers
  langfuse_prompt_id                                         prompt_id        FK → prompts
  active BOOL                                                config JSONB
                                                             │  (confidence_threshold,
                                                             │   concurrency,
                                                             │   notification_endpoint)
                                                             │ active BOOL
                                                             │ created_at
                                                             │
                                                             │ FK: pipeline_id
                                                             ▼
                                                         documents
                                                           doc_id       PK
                                                           filename
                                                           pipeline_id  FK → pipelines
                                                           created_at
                                                             │
                                          ┌──────────────────┼───────────────────┐
                                          ▼                  ▼                   ▼
                                        rules            conflicts           executions
                                      (FK: doc_id)      (FK: doc_id)       (FK: doc_id)
```

### Key design decisions in this ER

| Decision | Reason |
|----------|--------|
| `config JSONB` on `pipelines` (not individual columns) | New config vars = add a key, no migration |
| `config JSONB` on `llm_providers` | Provider shapes differ (NVIDIA vs Bedrock fields are not the same) |
| `prompts` references Langfuse via `langfuse_prompt_id` | Langfuse owns content + version history; DB owns which version is active |
| `documents.pipeline_id` FK | Records which pipeline/config produced the rules for that doc |
| No `settings` table | Replaced by seeder + `pipelines.config` |

### PK / FK rule (for reference)

- **PK** — uniquely identifies one row in its own table.
- **FK** — lives on the **dependent / "many" side**. Ask: *"can this row exist without the other?"* The one that cannot holds the FK.

---

## Phase 1 — Types + Config + DB

### Files

```
shared_types/pipeline.py
shared_types/rules.py
shared_types/invoice.py
config/types.py
config/loader.py
db/models.py
db/connector.py
db/seeder.py
db/queries.py
```

### shared_types/pipeline.py

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class RawBlock:
    text: str
    page: int

@dataclass(frozen=True)
class Clause:
    id: str
    text: str
    page: int

@dataclass(frozen=True)
class EnrichedClause:
    id: str
    text: str
    page: int
    referenced_texts: list[str]

@dataclass(frozen=True)
class RawExtraction:
    clause_id: str
    condition_raw: dict[str, Any]
    action_raw: str
    exceptions_raw: list[str]

@dataclass(frozen=True)
class ValidatedExtraction:
    clause_id: str
    condition: dict[str, Any]
    action: str
    exceptions: list[str]
    confidence: float
```

### shared_types/rules.py

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ASTNode:
    op: str
    left: ASTNode | str | float
    right: ASTNode | str | float | None

@dataclass(frozen=True)
class RuleRecord:
    rule_id: str
    doc_id: str
    condition: ASTNode
    action: str
    confidence: float
    source_clauses: list[str]

@dataclass(frozen=True)
class ConflictReport:
    rule_ids: list[str]
    overlap_description: str
```

### shared_types/invoice.py

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class InvoiceRecord:
    invoice_id: str
    fields: dict[str, Any]

@dataclass(frozen=True)
class ExecutionResult:
    invoice_id: str
    doc_id: str
    decision: str
    triggered_rule_ids: list[str]
    reasons: list[str]
```

### config/types.py

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float
    max_tokens: int

@dataclass(frozen=True)
class ConcurrencyConfig:
    max_parallel_clauses: int

@dataclass(frozen=True)
class NotificationConfig:
    endpoint: str

@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig
    concurrency: ConcurrencyConfig
    notifications: NotificationConfig
```

### config/loader.py

Loads `AppConfig` from the DB (active pipeline + its linked provider).
Raises `ConfigError` at startup — crash before serving traffic.
`config.json` is gone; the seeder provides the defaults.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from config.types import AppConfig, LLMConfig, ConcurrencyConfig, NotificationConfig
from db import queries

class ConfigError(Exception):
    pass

async def load_config_from_db(session: AsyncSession) -> AppConfig:
    try:
        pipeline = await queries.fetch_active_pipeline(session)
        provider = await queries.fetch_provider(session, pipeline.llm_provider_id)
    except (RuntimeError, KeyError) as exc:
        raise ConfigError(str(exc)) from exc

    pcfg = pipeline.config
    vcfg = provider.config
    try:
        return AppConfig(
            llm=LLMConfig(
                provider=provider.type,
                model=vcfg["model"],
                temperature=vcfg["temperature"],
                max_tokens=vcfg["max_tokens"],
            ),
            concurrency=ConcurrencyConfig(
                max_parallel_clauses=pcfg["concurrency"],
            ),
            notifications=NotificationConfig(
                endpoint=pcfg.get("notification_endpoint", ""),
            ),
            pipeline_id=pipeline.pipeline_id,
            confidence_threshold=pcfg["confidence_threshold"],
        )
    except KeyError as exc:
        raise ConfigError(f"Missing config key in DB: {exc}") from exc
```

> `AppConfig` gains two new fields: `pipeline_id: str` and `confidence_threshold: float`.
> Update `config/types.py` accordingly.

### db/models.py

7 tables. `settings` is removed. `llm_providers`, `prompts`, `pipelines` are new.
`documents` gains a `pipeline_id` FK. All app/processing config lives in `config JSONB` columns — no individual config columns, so adding new config vars never requires a migration.

```python
from sqlalchemy import Column, String, Float, JSON, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class LLMProviderModel(Base):
    __tablename__ = "llm_providers"
    provider_id = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    type        = Column(String, nullable=False)   # nvidia | bedrock | openrouter
    config      = Column(JSON, nullable=False)
    # config: { model, temperature, max_tokens, base_url, ... }
    # shape differs per provider type — JSONB avoids forcing a shared schema
    active      = Column(Boolean, nullable=False, default=True)

class PromptModel(Base):
    __tablename__ = "prompts"
    prompt_id          = Column(String, primary_key=True)
    name               = Column(String, nullable=False)
    version            = Column(Integer, nullable=False)
    langfuse_prompt_id = Column(String, nullable=True)   # set after Langfuse is wired
    # Langfuse is source of truth for content + version history.
    # DB owns which (name, version) is active for a given pipeline.
    active             = Column(Boolean, nullable=False, default=True)

class PipelineModel(Base):
    __tablename__ = "pipelines"
    pipeline_id     = Column(String, primary_key=True)
    name            = Column(String, nullable=False)
    llm_provider_id = Column(String, ForeignKey("llm_providers.provider_id"), nullable=False)
    prompt_id       = Column(String, ForeignKey("prompts.prompt_id"), nullable=False)
    config          = Column(JSON, nullable=False)
    # config: { confidence_threshold, concurrency, notification_endpoint }
    # confidence_threshold: rules below this value → status=pending_review
    # All pipeline-level settings go here; new keys need no migration.
    active          = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

class DocumentModel(Base):
    __tablename__ = "documents"
    doc_id      = Column(String, primary_key=True)
    filename    = Column(String, nullable=False)
    pipeline_id = Column(String, ForeignKey("pipelines.pipeline_id"), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class RuleModel(Base):
    __tablename__ = "rules"
    rule_id         = Column(String, primary_key=True)
    doc_id          = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    condition       = Column(JSON, nullable=False)
    action          = Column(String, nullable=False)
    confidence      = Column(Float, nullable=False)
    source_clauses  = Column(JSON, nullable=False)
    status          = Column(String, nullable=False, default="auto_approved")
    # status values: auto_approved | pending_review | reviewed
    override_action = Column(String, nullable=True)

class ConflictModel(Base):
    __tablename__ = "conflicts"
    conflict_id         = Column(String, primary_key=True)
    doc_id              = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    rule_ids            = Column(JSON, nullable=False)
    overlap_description = Column(String, nullable=False)

class ExecutionModel(Base):
    __tablename__ = "executions"
    execution_id       = Column(String, primary_key=True)
    invoice_id         = Column(String, nullable=False)
    doc_id             = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    decision           = Column(String, nullable=False)
    triggered_rule_ids = Column(JSON, nullable=False)
    reasons            = Column(JSON, nullable=False)
    executed_at        = Column(DateTime(timezone=True), server_default=func.now())
```

### db/connector.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from db.models import Base

class DBConnector:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    def session(self) -> AsyncSession:
        return self._session_factory()

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
```

### db/seeder.py

Runs once inside `create_tables()` on first boot. Inserts default rows only if the table is empty — safe to call on every restart.
`config.json` is deleted; these seeded values replace it entirely.

```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import LLMProviderModel, PromptModel, PipelineModel

async def seed_defaults(session: AsyncSession) -> None:
    provider = await _seed_llm_provider(session)
    prompt   = await _seed_prompt(session)
    await _seed_pipeline(session, provider.provider_id, prompt.prompt_id)
    await session.commit()

async def _seed_llm_provider(session: AsyncSession) -> LLMProviderModel:
    result = await session.execute(select(LLMProviderModel).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    provider = LLMProviderModel(
        provider_id=f"P-{uuid.uuid4().hex[:8].upper()}",
        name="OpenRouter Default",
        type="openrouter",
        config={
            # extraction default — fast, stable JSON output
            "model": "meta-llama/llama-3-8b-instruct",
            "temperature": 0.1,
            "max_tokens": 2048,
            "base_url": "https://openrouter.ai/api/v1",
        },
        active=True,
    )
    session.add(provider)
    return provider

async def _seed_prompt(session: AsyncSession) -> PromptModel:
    result = await session.execute(select(PromptModel).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    prompt = PromptModel(
        prompt_id=f"PR-{uuid.uuid4().hex[:8].upper()}",
        name="extraction",
        version=1,
        langfuse_prompt_id=None,   # wired after Langfuse is set up in Phase 9
        active=True,
    )
    session.add(prompt)
    return prompt

async def _seed_pipeline(
    session: AsyncSession,
    llm_provider_id: str,
    prompt_id: str,
) -> None:
    result = await session.execute(select(PipelineModel).limit(1))
    if result.scalar_one_or_none():
        return
    session.add(PipelineModel(
        pipeline_id=f"PL-{uuid.uuid4().hex[:8].upper()}",
        name="Default Extraction Pipeline",
        llm_provider_id=llm_provider_id,
        prompt_id=prompt_id,
        config={
            "confidence_threshold": 0.5,
            "concurrency": 5,
            "notification_endpoint": "",
        },
        active=True,
    ))
```

### db/queries.py

All DB I/O lives here only. ASTNode serialised via `dataclasses.asdict`.

```python
import uuid, dataclasses
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import (
    DocumentModel, RuleModel, ConflictModel, ExecutionModel,
    LLMProviderModel, PromptModel, PipelineModel,
)
from shared_types.rules import RuleRecord, ConflictReport, ASTNode
from shared_types.invoice import ExecutionResult

# ── provider / prompt / pipeline ─────────────────────────────────────────────

async def fetch_active_pipeline(session: AsyncSession) -> PipelineModel:
    result = await session.execute(select(PipelineModel).where(PipelineModel.active == True))
    row = result.scalar_one_or_none()
    if row is None:
        raise RuntimeError("No active pipeline found — run seeder first")
    return row

async def fetch_provider(session: AsyncSession, provider_id: str) -> LLMProviderModel:
    result = await session.execute(
        select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"provider_id={provider_id!r} not found")
    return row

async def fetch_prompt(session: AsyncSession, prompt_id: str) -> PromptModel:
    result = await session.execute(
        select(PromptModel).where(PromptModel.prompt_id == prompt_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"prompt_id={prompt_id!r} not found")
    return row

async def update_pipeline_config(
    session: AsyncSession, pipeline_id: str, config: dict
) -> PipelineModel:
    result = await session.execute(
        select(PipelineModel).where(PipelineModel.pipeline_id == pipeline_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"pipeline_id={pipeline_id!r} not found")
    row.config = config
    return row

async def update_provider_config(
    session: AsyncSession, provider_id: str, config: dict
) -> LLMProviderModel:
    result = await session.execute(
        select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"provider_id={provider_id!r} not found")
    row.config = config
    return row

# ── documents / rules / conflicts / executions ───────────────────────────────

async def insert_document(
    session: AsyncSession, doc_id: str, filename: str, pipeline_id: str
) -> None:
    session.add(DocumentModel(doc_id=doc_id, filename=filename, pipeline_id=pipeline_id))

async def insert_rule(session: AsyncSession, rule: RuleRecord, status: str) -> None:
    session.add(RuleModel(
        rule_id=rule.rule_id,
        doc_id=rule.doc_id,
        condition=dataclasses.asdict(rule.condition),
        action=rule.action,
        confidence=rule.confidence,
        source_clauses=rule.source_clauses,
        status=status,
    ))

async def insert_conflict(session: AsyncSession, doc_id: str, report: ConflictReport) -> None:
    session.add(ConflictModel(
        conflict_id=f"C-{uuid.uuid4().hex[:8].upper()}",
        doc_id=doc_id,
        rule_ids=report.rule_ids,
        overlap_description=report.overlap_description,
    ))

async def fetch_rules_by_doc(session: AsyncSession, doc_id: str) -> list[RuleRecord]:
    result = await session.execute(select(RuleModel).where(RuleModel.doc_id == doc_id))
    return [_row_to_rule(row) for row in result.scalars().all()]

async def insert_execution(session: AsyncSession, result: ExecutionResult) -> None:
    session.add(ExecutionModel(
        execution_id=f"E-{uuid.uuid4().hex[:8].upper()}",
        invoice_id=result.invoice_id,
        doc_id=result.doc_id,
        decision=result.decision,
        triggered_rule_ids=result.triggered_rule_ids,
        reasons=result.reasons,
    ))

async def fetch_rule_by_id(session: AsyncSession, rule_id: str) -> RuleModel | None:
    result = await session.execute(select(RuleModel).where(RuleModel.rule_id == rule_id))
    return result.scalar_one_or_none()

async def fetch_pending_review_rules(session: AsyncSession) -> list[RuleModel]:
    result = await session.execute(select(RuleModel).where(RuleModel.status == "pending_review"))
    return list(result.scalars().all())

async def update_rule_review(
    session: AsyncSession, rule_id: str, override_action: str,
) -> None:
    result = await session.execute(select(RuleModel).where(RuleModel.rule_id == rule_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"rule_id={rule_id!r} not found")
    row.override_action = override_action
    row.status = "reviewed"

# ── helpers ───────────────────────────────────────────────────────────────────

def _row_to_rule(row: RuleModel) -> RuleRecord:
    return RuleRecord(
        rule_id=row.rule_id,
        doc_id=row.doc_id,
        condition=_dict_to_ast(row.condition),
        action=row.action,
        confidence=row.confidence,
        source_clauses=row.source_clauses,
    )

def _dict_to_ast(d: dict) -> ASTNode:
    left = d["left"]
    right = d.get("right")
    return ASTNode(
        op=d["op"],
        left=_dict_to_ast(left) if isinstance(left, dict) else left,
        right=_dict_to_ast(right) if isinstance(right, dict) else right,
    )
```

---

## Phase 2 — LLM Abstraction

### Files

```
llm/prompts.py
llm/client.py
```

### llm/prompts.py

```python
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
```

### llm/client.py

```python
import asyncio, logging
from openai import AsyncOpenAI
from config.types import LLMConfig

logger = logging.getLogger(__name__)

class LLMCallError(Exception):
    pass

class LLMClient:
    def __init__(
        self,
        config: LLMConfig,
        nvidia_api_key: str,
        openrouter_api_key: str,
        aws_credentials: dict,
    ) -> None:
        self._config = config
        if config.provider == "nvidia":
            self._openai = AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=nvidia_api_key,
            )
        elif config.provider == "openrouter":
            self._openai = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_api_key,
            )
        elif config.provider == "bedrock":
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", **aws_credentials)

    async def generate(self, prompt: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return await self._call(prompt)
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning("llm_retry", extra={"attempt": attempt, "wait": wait, "error": str(exc)})
                await asyncio.sleep(wait)
        raise LLMCallError("LLM call failed after 3 attempts") from last_exc

    async def _call(self, prompt: str) -> str:
        if self._config.provider in ("nvidia", "openrouter"):
            return await self._openai_call(prompt)
        return await self._bedrock_call(prompt)

    async def _openai_call(self, prompt: str) -> str:
        resp = await self._openai.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return resp.choices[0].message.content

    async def _bedrock_call(self, prompt: str) -> str:
        import json
        body = json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": self._config.max_tokens,
            "temperature": self._config.temperature,
        })
        resp = self._bedrock.invoke_model(body=body, modelId=self._config.model,
                                          contentType="application/json")
        return json.loads(resp["body"].read())["completion"]
```

---

## Phase 3 — Pipeline Steps

No step imports another step. Only `shared_types` and `llm` are imported.

### Files

```
pipeline/parser.py
pipeline/splitter.py
pipeline/xref_resolver.py
pipeline/llm_extractor.py
pipeline/validator.py
pipeline/rule_builder.py
pipeline/conflict_detector.py
```

### pipeline/parser.py

```python
import fitz
from shared_types.pipeline import RawBlock

def parse_pdf(file_path: str) -> list[RawBlock]:
    doc = fitz.open(file_path)
    blocks: list[RawBlock] = []
    for page_num, page in enumerate(doc, start=1):
        for block in page.get_text("blocks"):
            text = block[4].strip()
            if text:
                blocks.append(RawBlock(text=text, page=page_num))
    return blocks
```

### pipeline/splitter.py

```python
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
```

### pipeline/xref_resolver.py

```python
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
```

### pipeline/llm_extractor.py

```python
import json
from shared_types.pipeline import EnrichedClause, RawExtraction
from llm.client import LLMClient
from llm.prompts import EXTRACTION_PROMPT
from config.types import LLMConfig

class ExtractionError(Exception):
    pass

async def extract_clause(clause: EnrichedClause, llm: LLMClient, config: LLMConfig) -> RawExtraction:
    context = clause.text
    if clause.referenced_texts:
        context += "\n\nReferenced:\n" + "\n".join(clause.referenced_texts)
    raw = await llm.generate(EXTRACTION_PROMPT.format(clause_text=context))
    try:
        parsed = json.loads(raw.strip().strip("```json").strip("```").strip())
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"JSON parse failed for clause {clause.id!r}") from exc
    return RawExtraction(
        clause_id=clause.id,
        condition_raw=parsed.get("condition", {}),
        action_raw=parsed.get("action", ""),
        exceptions_raw=parsed.get("exceptions", []),
    )
```

### pipeline/validator.py

```python
from shared_types.pipeline import RawExtraction, ValidatedExtraction

VALID_OPS = {">", "<", ">=", "<=", "==", "AND", "OR", "NOT", "*", "+"}
VALID_ACTIONS = {"APPROVE", "ESCALATE", "REJECT"}

class ValidationError(Exception):
    pass

def validate_extraction(raw: RawExtraction) -> ValidatedExtraction:
    if not raw.condition_raw:
        raise ValidationError(f"Missing condition in {raw.clause_id!r}")
    if raw.action_raw not in VALID_ACTIONS:
        raise ValidationError(f"Invalid action {raw.action_raw!r} in {raw.clause_id!r}")
    _check_ops(raw.condition_raw, raw.clause_id)
    return ValidatedExtraction(
        clause_id=raw.clause_id,
        condition=raw.condition_raw,
        action=raw.action_raw,
        exceptions=raw.exceptions_raw,
        confidence=1.0,
    )

def _check_ops(node: dict, clause_id: str) -> None:
    op = node.get("op")
    if op and op not in VALID_OPS:
        raise ValidationError(f"Unknown op {op!r} in {clause_id!r}")
    for key in ("left", "right"):
        child = node.get(key)
        if isinstance(child, dict):
            _check_ops(child, clause_id)
```

### pipeline/rule_builder.py

```python
import uuid
from shared_types.pipeline import ValidatedExtraction
from shared_types.rules import ASTNode, RuleRecord

class ASTBuildError(Exception):
    pass

def build_rule(validated: ValidatedExtraction, doc_id: str) -> RuleRecord:
    return RuleRecord(
        rule_id=f"R-{uuid.uuid4().hex[:8].upper()}",
        doc_id=doc_id,
        condition=_build_ast(validated.condition, validated.clause_id),
        action=validated.action,
        confidence=validated.confidence,
        source_clauses=[validated.clause_id],
    )

def _build_ast(node: dict | str | float | int, clause_id: str) -> ASTNode | str | float:
    if not isinstance(node, dict):
        return node
    op = node.get("op")
    if not op:
        raise ASTBuildError(f"Node missing 'op' in {clause_id!r}: {node!r}")
    left = _build_ast(node.get("left", ""), clause_id)
    right = _build_ast(node["right"], clause_id) if "right" in node else None
    return ASTNode(op=op, left=left, right=right)
```

### pipeline/conflict_detector.py

```python
from shared_types.rules import RuleRecord, ConflictReport, ASTNode

def detect_conflicts(rules: list[RuleRecord]) -> list[ConflictReport]:
    numeric = [r for r in rules if _is_numeric(r.condition)]
    conflicts: list[ConflictReport] = []
    for i, r1 in enumerate(numeric):
        for r2 in numeric[i + 1:]:
            if r1.action != r2.action and _same_field(r1.condition, r2.condition):
                conflicts.append(ConflictReport(
                    rule_ids=[r1.rule_id, r2.rule_id],
                    overlap_description=(
                        f"{r1.rule_id} ({r1.action}) conflicts with {r2.rule_id} ({r2.action})"
                    ),
                ))
    return conflicts

def _is_numeric(node: ASTNode | str | float) -> bool:
    return isinstance(node, ASTNode) and node.op in {">", "<", ">=", "<="}

def _same_field(n1: ASTNode, n2: ASTNode) -> bool:
    return n1.left == n2.left
```

---

## Phase 4 — Orchestrator

### pipeline/orchestrator.py

```python
import asyncio, json, logging
from shared_types.pipeline import EnrichedClause, RawExtraction, ValidatedExtraction
from shared_types.rules import RuleRecord
from pipeline.parser import parse_pdf
from pipeline.splitter import split_into_clauses
from pipeline.xref_resolver import resolve_references
from pipeline.llm_extractor import extract_clause, ExtractionError
from pipeline.validator import validate_extraction, ValidationError
from pipeline.rule_builder import build_rule
from pipeline.conflict_detector import detect_conflicts
from llm.client import LLMClient
from llm.prompts import RETRY_EXTRACTION_PROMPT
from config.types import AppConfig
from db.connector import DBConnector
from db import queries

logger = logging.getLogger(__name__)

DEFAULT_REVIEW_THRESHOLD = 0.5

async def run_pipeline(
    file_path: str,
    doc_id: str,
    config: AppConfig,
    llm: LLMClient,
    db: DBConnector,
) -> list[RuleRecord]:
    blocks = parse_pdf(file_path)
    clauses = split_into_clauses(blocks)
    enriched = resolve_references(clauses)

    sem = asyncio.Semaphore(config.concurrency.max_parallel_clauses)
    results = await asyncio.gather(*[_process(c, doc_id, config, llm, sem) for c in enriched])
    rules = [r for r in results if r is not None]
    conflicts = detect_conflicts(rules)

    async with db.session() as session:
        raw_threshold = await queries.get_setting(session, "review_confidence_threshold")
        threshold = float(raw_threshold) if raw_threshold else DEFAULT_REVIEW_THRESHOLD
        for rule in rules:
            status = "pending_review" if rule.confidence < threshold else "auto_approved"
            await queries.insert_rule(session, rule, status=status)
        for conflict in conflicts:
            await queries.insert_conflict(session, doc_id, conflict)
        await session.commit()

    return rules

async def _process(
    clause: EnrichedClause,
    doc_id: str,
    config: AppConfig,
    llm: LLMClient,
    sem: asyncio.Semaphore,
) -> RuleRecord | None:
    async with sem:
        try:
            raw = await extract_clause(clause, llm, config.llm)
            validated = validate_extraction(raw)
        except (ExtractionError, ValidationError) as exc:
            logger.warning("extraction_retry", extra={"clause_id": clause.id, "error": str(exc)})
            try:
                text = await llm.generate(RETRY_EXTRACTION_PROMPT.format(clause_text=clause.text))
                parsed = json.loads(text.strip())
                raw = RawExtraction(
                    clause_id=clause.id,
                    condition_raw=parsed.get("condition", {}),
                    action_raw=parsed.get("action", ""),
                    exceptions_raw=parsed.get("exceptions", []),
                )
                v = validate_extraction(raw)
                validated = ValidatedExtraction(
                    clause_id=v.clause_id, condition=v.condition,
                    action=v.action, exceptions=v.exceptions, confidence=0.5,
                )
            except Exception as retry_exc:
                logger.warning("extraction_failed", extra={"clause_id": clause.id, "error": str(retry_exc)})
                return None

        return build_rule(validated, doc_id)
```

---

## Phase 5 — Execution Engine

### engine/evaluator.py

```python
from typing import Any
from shared_types.rules import ASTNode
from shared_types.invoice import InvoiceRecord

class EvaluationError(Exception):
    pass

def evaluate_node(node: ASTNode | str | float | int, invoice: InvoiceRecord) -> Any:
    if isinstance(node, str):
        return invoice.fields.get(node, node)
    if isinstance(node, (int, float)):
        return node
    if not isinstance(node, ASTNode):
        raise EvaluationError(f"Unexpected node type: {type(node)!r}")
    left = evaluate_node(node.left, invoice)
    right = evaluate_node(node.right, invoice) if node.right is not None else None
    match node.op:
        case ">":   return left > right
        case "<":   return left < right
        case ">=":  return left >= right
        case "<=":  return left <= right
        case "==":  return left == right
        case "*":   return left * right
        case "+":   return left + right
        case "AND": return bool(left) and bool(right)
        case "OR":  return bool(left) or bool(right)
        case "NOT": return not bool(left)
        case _:     raise EvaluationError(f"Unknown op: {node.op!r}")
```

### engine/executor.py

```python
from shared_types.rules import RuleRecord
from shared_types.invoice import InvoiceRecord, ExecutionResult
from engine.evaluator import evaluate_node

PRIORITY = {"REJECT": 3, "ESCALATE": 2, "APPROVE": 1}

def execute_rules(rules: list[RuleRecord], invoice: InvoiceRecord, doc_id: str) -> ExecutionResult:
    triggered = [r for r in rules if _matches(r, invoice)]
    if not triggered:
        return ExecutionResult(
            invoice_id=invoice.invoice_id, doc_id=doc_id,
            decision="APPROVE", triggered_rule_ids=[], reasons=["No rules triggered"],
        )
    winner = max(triggered, key=lambda r: PRIORITY[r.action])
    return ExecutionResult(
        invoice_id=invoice.invoice_id, doc_id=doc_id,
        decision=winner.action,
        triggered_rule_ids=[r.rule_id for r in triggered],
        reasons=[f"{r.rule_id} matched ({r.action})" for r in triggered],
    )

def _matches(rule: RuleRecord, invoice: InvoiceRecord) -> bool:
    try:
        return bool(evaluate_node(rule.condition, invoice))
    except Exception:
        return False
```

---

## Phase 6 — Notifications + Visualization

### notifications/dispatcher.py

Requires `httpx` — **confirm before adding to requirements.txt**.

```python
import httpx, logging
from shared_types.invoice import ExecutionResult
from config.types import NotificationConfig

logger = logging.getLogger(__name__)

async def dispatch(result: ExecutionResult, config: NotificationConfig) -> None:
    if not config.endpoint:
        return
    payload = {
        "invoice_id": result.invoice_id, "doc_id": result.doc_id,
        "decision": result.decision, "triggered_rule_ids": result.triggered_rule_ids,
        "reasons": result.reasons,
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(config.endpoint, json=payload, timeout=10.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("dispatch_failed", extra={"invoice_id": result.invoice_id, "error": str(exc)})
```

### visualization/graph_builder.py

```python
from dataclasses import dataclass
from shared_types.rules import RuleRecord

@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    action: str

@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str

@dataclass(frozen=True)
class GraphData:
    nodes: list[GraphNode]
    edges: list[GraphEdge]

def build_dependency_graph(rules: list[RuleRecord]) -> GraphData:
    nodes = [GraphNode(id=r.rule_id, label=f"{r.rule_id} ({r.action})", action=r.action)
             for r in rules]
    edges = [GraphEdge(source=cid, target=r.rule_id)
             for r in rules for cid in r.source_clauses]
    return GraphData(nodes=nodes, edges=edges)
```

---

## Phase 7 — API Layer

### Files

```
api/schemas.py
api/dependencies.py
api/routes.py
main.py  (update)
```

### api/schemas.py

```python
from pydantic import BaseModel
from typing import Any

class UploadResponse(BaseModel):
    doc_id: str
    rule_count: int
    conflict_count: int

class RuleResponse(BaseModel):
    rule_id: str
    action: str
    confidence: float
    source_clauses: list[str]
    condition: dict[str, Any]

class RulesListResponse(BaseModel):
    doc_id: str
    rules: list[RuleResponse]

class ExecuteRequest(BaseModel):
    doc_id: str
    invoice: dict[str, Any]

class ExecuteResponse(BaseModel):
    decision: str
    triggered_rule_ids: list[str]
    reasons: list[str]

class PatchRuleRequest(BaseModel):
    override_action: str  # APPROVE | ESCALATE | REJECT

class ReviewRuleResponse(BaseModel):
    rule_id: str
    doc_id: str
    action: str
    confidence: float
    source_clauses: list[str]
    condition: dict[str, Any]
    status: str
    override_action: str | None

class ReviewQueueResponse(BaseModel):
    rules: list[ReviewRuleResponse]

class ReviewThresholdResponse(BaseModel):
    threshold: float

class ReviewThresholdRequest(BaseModel):
    threshold: float
```

### api/dependencies.py

```python
import os
from functools import lru_cache
from config.loader import load_config
from config.types import AppConfig
from llm.client import LLMClient
from db.connector import DBConnector

@lru_cache
def get_config() -> AppConfig:
    return load_config("config.json")

@lru_cache
def get_db() -> DBConnector:
    return DBConnector(os.environ["DATABASE_URL"])

@lru_cache
def get_llm() -> LLMClient:
    cfg = get_config()
    return LLMClient(
        config=cfg.llm,
        nvidia_api_key=os.environ.get("NVIDIA_API_KEY", ""),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        aws_credentials={
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            "region_name": os.environ.get("AWS_REGION", "us-east-1"),
        },
    )
```

### api/routes.py

```python
import os, uuid, dataclasses
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.schemas import (
    UploadResponse, RulesListResponse, ExecuteRequest, ExecuteResponse,
    PatchRuleRequest, ReviewQueueResponse, ReviewRuleResponse,
    ReviewThresholdResponse, ReviewThresholdRequest,
)
from api.dependencies import get_config, get_llm, get_db
from pipeline.orchestrator import run_pipeline
from pipeline.conflict_detector import detect_conflicts
from engine.executor import execute_rules
from notifications.dispatcher import dispatch
from db import queries
from shared_types.invoice import InvoiceRecord

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_policy(file: UploadFile):
    config = get_config()
    llm = get_llm()
    db = get_db()
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    tmp = f"/tmp/{doc_id}.pdf"
    try:
        with open(tmp, "wb") as f:
            f.write(await file.read())
        async with db.session() as session:
            await queries.insert_document(session, doc_id, file.filename or "unknown.pdf")
            await session.commit()
        rules = await run_pipeline(tmp, doc_id, config, llm, db)
        conflicts = detect_conflicts(rules)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return UploadResponse(doc_id=doc_id, rule_count=len(rules), conflict_count=len(conflicts))

@router.get("/rules/{doc_id}", response_model=RulesListResponse)
async def get_rules(doc_id: str):
    db = get_db()
    async with db.session() as session:
        rules = await queries.fetch_rules_by_doc(session, doc_id)
    if not rules:
        raise HTTPException(404, f"No rules for doc_id={doc_id!r}")
    return RulesListResponse(
        doc_id=doc_id,
        rules=[{"rule_id": r.rule_id, "action": r.action, "confidence": r.confidence,
                "source_clauses": r.source_clauses, "condition": dataclasses.asdict(r.condition)}
               for r in rules],
    )

@router.post("/execute", response_model=ExecuteResponse)
async def execute(body: ExecuteRequest):
    config = get_config()
    db = get_db()
    async with db.session() as session:
        rules = await queries.fetch_rules_by_doc(session, body.doc_id)
    if not rules:
        raise HTTPException(404, f"No rules for doc_id={body.doc_id!r}")
    invoice = InvoiceRecord(
        invoice_id=body.invoice.get("invoice_id", f"INV-{uuid.uuid4().hex[:8]}"),
        fields=body.invoice,
    )
    result = execute_rules(rules, invoice, body.doc_id)
    async with db.session() as session:
        await queries.insert_execution(session, result)
        await session.commit()
    await dispatch(result, config.notifications)
    return ExecuteResponse(
        decision=result.decision,
        triggered_rule_ids=result.triggered_rule_ids,
        reasons=result.reasons,
    )

@router.get("/review", response_model=ReviewQueueResponse)
async def get_review_queue():
    db = get_db()
    async with db.session() as session:
        rows = await queries.fetch_pending_review_rules(session)
    return ReviewQueueResponse(rules=[
        ReviewRuleResponse(
            rule_id=r.rule_id, doc_id=r.doc_id, action=r.action,
            confidence=r.confidence, source_clauses=r.source_clauses,
            condition=r.condition, status=r.status, override_action=r.override_action,
        )
        for r in rows
    ])

@router.patch("/rules/{rule_id}", response_model=ReviewRuleResponse)
async def patch_rule(rule_id: str, body: PatchRuleRequest):
    if body.override_action not in {"APPROVE", "ESCALATE", "REJECT"}:
        raise HTTPException(400, f"Invalid action: {body.override_action!r}")
    db = get_db()
    async with db.session() as session:
        try:
            await queries.update_rule_review(session, rule_id, body.override_action)
            await session.commit()
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        row = await queries.fetch_rule_by_id(session, rule_id)
    return ReviewRuleResponse(
        rule_id=row.rule_id, doc_id=row.doc_id, action=row.action,
        confidence=row.confidence, source_clauses=row.source_clauses,
        condition=row.condition, status=row.status, override_action=row.override_action,
    )

@router.get("/settings/review-threshold", response_model=ReviewThresholdResponse)
async def get_review_threshold():
    db = get_db()
    async with db.session() as session:
        raw = await queries.get_setting(session, "review_confidence_threshold")
    return ReviewThresholdResponse(threshold=float(raw) if raw else 0.5)

@router.patch("/settings/review-threshold", response_model=ReviewThresholdResponse)
async def set_review_threshold(body: ReviewThresholdRequest):
    if not (0.0 <= body.threshold <= 1.0):
        raise HTTPException(400, "threshold must be between 0.0 and 1.0")
    db = get_db()
    async with db.session() as session:
        await queries.set_setting(session, "review_confidence_threshold", str(body.threshold))
        await session.commit()
    return ReviewThresholdResponse(threshold=body.threshold)
```

### main.py (updated)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes import router
from api.dependencies import get_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db().create_tables()
    yield

app = FastAPI(title="CashFlo Policy Engine", version="0.1.0", lifespan=lifespan)
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Phase 8 — UI

Next.js 14 + **shadcn/ui**. All pages communicate with the API through a typed `lib/api.ts`.

### Setup

```bash
npx shadcn@latest init          # choose default style + CSS vars
npx shadcn@latest add card badge slider button table input label select dialog
```

### shadcn/ui component map

| Component | Used in |
|-----------|---------|
| `Card` | `RuleCard`, `ReviewCard` — wraps each rule/review item |
| `Badge` | `ConfidenceBadge` — green / amber / red variant |
| `Slider` + `Input` | `ThresholdSlider` on `/settings` |
| `Button` | Approve / Escalate / Reject actions, Save, Upload |
| `Table` | `/rules/[docId]` — rules list |
| `Dialog` | Confirmation before submitting a review override |
| `Select` | Provider / pipeline selector on `/settings` |
| `Label` + `Input` | Config edit forms on `/settings` |

### Files to create

```
ui/src/lib/api.ts
ui/src/app/upload/page.tsx
ui/src/app/rules/[docId]/page.tsx
ui/src/app/execute/page.tsx
ui/src/app/review/page.tsx
ui/src/app/settings/page.tsx
ui/src/app/settings/pipeline/page.tsx
ui/src/app/settings/provider/page.tsx
ui/src/components/RuleCard.tsx
ui/src/components/DecisionBanner.tsx
ui/src/components/ConfidenceBadge.tsx
ui/src/components/ReviewCard.tsx
ui/src/components/ThresholdSlider.tsx
ui/src/components/ConfigEditor.tsx
```

### lib/api.ts

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type UploadResponse = { doc_id: string; rule_count: number; conflict_count: number }
export type RuleResponse = { rule_id: string; action: string; confidence: number; source_clauses: string[]; condition: object }
export type RulesListResponse = { doc_id: string; rules: RuleResponse[] }
export type ExecuteRequest = { doc_id: string; invoice: Record<string, unknown> }
export type ExecuteResponse = { decision: string; triggered_rule_ids: string[]; reasons: string[] }

export async function uploadPolicy(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getRules(docId: string): Promise<RulesListResponse> {
  const res = await fetch(`${BASE}/rules/${docId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function executeRules(req: ExecuteRequest): Promise<ExecuteResponse> {
  const res = await fetch(`${BASE}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export type ReviewRuleResponse = {
  rule_id: string; doc_id: string; action: string; confidence: number
  source_clauses: string[]; condition: object; status: string; override_action: string | null
}
export type ReviewQueueResponse = { rules: ReviewRuleResponse[] }

export async function getReviewQueue(): Promise<ReviewQueueResponse> {
  const res = await fetch(`${BASE}/review`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function patchRule(ruleId: string, overrideAction: string): Promise<ReviewRuleResponse> {
  const res = await fetch(`${BASE}/rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ override_action: overrideAction }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getReviewThreshold(): Promise<{ threshold: number }> {
  const res = await fetch(`${BASE}/settings/review-threshold`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function setReviewThreshold(threshold: number): Promise<{ threshold: number }> {
  const res = await fetch(`${BASE}/settings/review-threshold`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ threshold }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

### Page responsibilities

| Page | Input | Output |
|------|-------|--------|
| `/upload` | `Button` + file picker | doc_id + rule count + conflict count, link to rules page |
| `/rules/[docId]` | doc_id from URL | shadcn `Table` of rules; `Badge` for confidence; source clauses; low-confidence flagged |
| `/execute` | doc_id + invoice JSON textarea | `DecisionBanner` (APPROVE/ESCALATE/REJECT) + triggered rules list |
| `/review` | none | `ReviewCard` list — confidence `Badge`, extracted action, source clause; Approve/Escalate/Reject `Button`s; `Dialog` confirm before submit |
| `/settings` | none | `ThresholdSlider` for confidence threshold; links to pipeline and provider sub-pages |
| `/settings/pipeline` | none | `ConfigEditor` — loads active pipeline `config` JSONB via `GET /config/pipeline`; saves via `PATCH /config/pipeline` |
| `/settings/provider` | none | `ConfigEditor` — loads active provider `config` JSONB via `GET /config/provider`; saves via `PATCH /config/provider`. Includes a `Select` for provider type (`nvidia` / `openrouter` / `bedrock`) and a model `Select` whose options update based on the chosen provider (see OpenRouter model catalogue below) |

### OpenRouter model catalogue (used in `/settings/provider` Select)

Two groups are shown in the `Select` component; the group label explains the intended use.

**Extraction** (default — fast, stable JSON output)

| Display label | OpenRouter model ID |
|---------------|---------------------|
| Llama 3 8B Instruct *(default)* | `meta-llama/llama-3-8b-instruct` |

**Answer generation / RAG** (better reasoning, multi-chunk context)

| Display label | OpenRouter model ID | Notes |
|---------------|---------------------|-------|
| Mixtral 8x7B Instruct | `mistralai/mixtral-8x7b-instruct` | Best free reasoning; handles long context well |
| Llama 3 70B Instruct | `meta-llama/llama-3-70b-instruct` | Strongest reasoning; may have rate limits on free tier |

The selected `model` value is stored in `llm_providers.config.model` (JSONB). Changing the model in the UI writes it via `PATCH /config/provider` — no code change or migration required.

`OPENROUTER_API_KEY` must be present in `.env`. When `provider.type == "openrouter"` and the key is empty the app raises `ConfigError` on startup.

---

### ConfidenceBadge thresholds

Thresholds are relative to the configurable review threshold `T` (default 0.5):

- confidence >= 0.8 → green
- confidence >= T → amber
- confidence < T → red + "Needs Review" label; rule is routed to `/review`

### ReviewCard behaviour

`ReviewCard` is used on `/review`. It shows:
- Rule ID, doc ID, extracted action, confidence (via ConfidenceBadge)
- Source clause text
- Three buttons: **Approve / Escalate / Reject** — calls `PATCH /rules/{rule_id}`
- On success the card disappears from the queue (optimistic remove)

### ThresholdSlider behaviour

`ThresholdSlider` is used on `/settings`. It shows:
- Current threshold value loaded from `GET /settings/review-threshold`
- A number input (step 0.05, min 0, max 1)
- A **Save** button — calls `PATCH /settings/review-threshold`; shows success/error inline
- Explanation text: "Rules extracted with confidence below this value will be queued for human review"

---

## Phase 9 — Production Hardening

Already done: `docker-compose.prod.yml`, nginx config.

Remaining items before production:

| Item | Action |
|------|--------|
| Alembic migrations | Replace `create_tables()` with `alembic upgrade head` in entrypoint; wire after first schema change in production |
| Langfuse tracing | Wrap orchestrator in `langfuse.trace()`; each step as a span |
| Structured logging init | `structlog.configure()` in `main.py` lifespan |
| DB seed for threshold setting | Insert `review_confidence_threshold=0.5` row in `settings` table on `create_tables()` if not present |

---

## Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Add `httpx` to `requirements.txt`? | Already present (`httpx>=0.27`) — no change needed |
| 2 | Alembic migrations now or after MVP validation? | After MVP — `create_tables()` is sufficient until first production schema change |
| 3 | Additional UI libraries (Tailwind, shadcn/ui)? | **Yes — shadcn/ui adopted.** Provides accessible, composable primitives (Card, Badge, Slider, Table, Dialog) without requiring a custom design system. Tailwind is included as shadcn/ui's peer dependency. |
| 4 | Include `PATCH /rules/{rule_id}` (human review)? | Yes, included in Phase 7; review queue and threshold configuration also added to Phase 8 UI |
| 5 | Centralised `configs` table vs config column per entity? | **Per-entity `config JSONB` column.** Centralised breaks when providers/pipelines multiply. Config belongs to the entity that owns it (`llm_providers.config`, `pipelines.config`). New keys never require a migration. Dedicated columns only when SQL needs to filter/sort/join on the field. |
| 6 | `config.json` as runtime config source? | **Removed.** Replaced by DB seeder (`db/seeder.py`) which inserts default rows on first boot. `.env` remains for secrets and `DATABASE_URL` only. |
| 7 | `settings` table (key-value)? | **Dropped.** `confidence_threshold` and all pipeline-level settings live in `pipelines.config JSONB`. No key-value store needed. |
| 8 | Prompt versioning — Langfuse vs DB? | **Both, linked.** Langfuse owns content + full version history. DB `prompts` table stores `(name, version, langfuse_prompt_id, active)` — the reference that tells a pipeline which version to fetch. Link key: `(name, version)` is the same in both systems. |
| 9 | `review_confidence_threshold` — column or JSONB key? | **JSONB key inside `pipelines.config`.** It is read in Python, never filtered in SQL, so a dedicated column adds no value and every new setting would require a migration. |
| 10 | LLM provider for default seed — NVIDIA or OpenRouter? | **OpenRouter.** Free tier covers the two required use cases without credentials beyond an API key: Llama 3 8B for extraction (fast, stable JSON) and Mixtral 8x7B / Llama 3 70B for RAG answer generation (better reasoning). NVIDIA and Bedrock remain supported via `provider.type` — users switch in `/settings/provider`. `LLMClient._nvidia_call` is renamed `_openai_call` since both NVIDIA and OpenRouter use the OpenAI-compatible API; only the `base_url` and key differ. |
