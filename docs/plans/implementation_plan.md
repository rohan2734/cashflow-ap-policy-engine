Implementation Plan: Policy-to-Rule Pipeline
0. Guiding Constraints (from CLAUDE.md)
Functional style everywhere; classes only for LLM client and DB connector
All types named — no anonymous shapes crossing function boundaries
No default parameter values — all explicit at call site
YAGNI — no speculative abstractions
Errors raised at point of failure with full context; retry + exponential backoff on external calls
Structured logging (no string interpolation into message strings)
No secrets in code; SQL via ORM/parameterised queries only
1. Project Directory Layout

/cashflo
  /api
    routes.py          ← FastAPI routers (upload, rules, execute)
    schemas.py         ← Pydantic request/response models
    dependencies.py    ← FastAPI dependency injection (DB session, LLM client)
  /pipeline
    parser.py          ← PDF → raw blocks
    splitter.py        ← raw blocks → clauses
    xref_resolver.py   ← clauses → context-enriched clauses
    llm_extractor.py   ← clauses → raw LLM output
    validator.py       ← raw LLM output → validated rule
    rule_builder.py    ← validated rule → AST rule
    conflict_detector.py ← [AST rule] → [AST rule] + conflict flags
    orchestrator.py    ← composes all pipeline steps
  /llm
    client.py          ← LLMClient class (NVIDIA / Bedrock)
    prompts.py         ← prompt templates as constants
  /engine
    executor.py        ← executes AST rule against invoice JSON
    evaluator.py       ← evaluates a single AST node
  /db
    connector.py       ← SQLAlchemy engine + session factory (class)
    models.py          ← ORM table definitions
    queries.py         ← all DB read/write as pure functions
  /notifications
    dispatcher.py      ← sends notifications based on execution result
  /visualization
    graph_builder.py   ← builds rule dependency graph data
  /config
    loader.py          ← loads + validates config.json at startup
    types.py           ← named config types
  /types
    pipeline.py        ← all shared pipeline type definitions
    rules.py           ← AST node types, RuleRecord, ConflictReport
    invoice.py         ← InvoiceRecord type
  main.py              ← FastAPI app factory + startup
  config.json          ← runtime config (LLM provider, concurrency, etc.)
  docker-compose.yml   ← Postgres + Langfuse only
  requirements.txt
  .env.example         ← documents required env vars; never commit .env
2. Named Type Definitions (/types/)
Define all shared shapes here before writing any pipeline code. Everything that crosses a function boundary must use one of these.

Type	Fields	Used by
RawBlock	text, page	parser → splitter
Clause	id, text, page	splitter → xref → extractor
EnrichedClause	id, text, page, referenced_texts	xref → extractor
RawExtraction	condition_raw, action_raw, exceptions_raw	extractor → validator
ValidatedExtraction	condition, action, exceptions, confidence	validator → rule_builder
ASTNode	op, left, right (recursive)	rule_builder → executor
RuleRecord	rule_id, doc_id, condition (AST), action, confidence, source_clauses	DB + executor
ConflictReport	rule_ids, overlap_description	conflict_detector → stored
InvoiceRecord	invoice_id, fields (dict)	executor
ExecutionResult	rule_id, invoice_id, decision, matched_clauses	executor → notifications
LLMConfig	provider, model, temperature, max_tokens	config → LLMClient
AppConfig	llm (LLMConfig), concurrency (ConcurrencyConfig)	loader → everywhere
3. Module Implementation Order
Dependencies flow top-to-bottom. Implement in this sequence.

Phase 1 — Foundation (no external calls)
/types/ — all named types; nothing else compiles without these
/config/loader.py — parse + validate config.json into AppConfig; raise ConfigError on missing required fields
/db/models.py — ORM table definitions: documents, rules, conflicts, executions
/db/connector.py — DBConnector class wrapping SQLAlchemy async session factory
/db/queries.py — pure functions: insert_rule, fetch_rules_by_doc, insert_execution, etc.
Phase 2 — LLM Abstraction
/llm/prompts.py — extraction prompt as a named constant template; no logic here
/llm/client.py — LLMClient class with async generate(prompt: str, config: LLMConfig) -> str
NVIDIA path + Bedrock path dispatched by config.provider
Retry with exponential backoff (max 2 retries); log each retry as WARNING with request params
Re-raise last error with full context (status code, response body)
Phase 3 — Pipeline Steps (pure functions)
Implement each as a module of pure functions. No step imports another pipeline step — only types.

/pipeline/parser.py — parse_pdf(file_path: str) -> list[RawBlock] using PyMuPDF
/pipeline/splitter.py — split_into_clauses(blocks: list[RawBlock]) -> list[Clause]
Regex-based on numbered patterns first
Heuristic fallback (IF/WHEN/SHALL keywords, sentence boundaries)
/pipeline/xref_resolver.py — resolve_references(clauses: list[Clause]) -> list[EnrichedClause]
Extract ref patterns, build adjacency map, DFS-resolve (cycle-safe with visited set)
/pipeline/llm_extractor.py — extract_clause(clause: EnrichedClause, llm: LLMClient, config: LLMConfig) -> RawExtraction
Single async function; semaphore applied at orchestrator level, not here
/pipeline/validator.py — validate_extraction(raw: RawExtraction) -> ValidatedExtraction
Check structure, operator whitelist, variable existence
On failure: raise ValidationError with clause id + raw output; caller decides retry
/pipeline/rule_builder.py — build_ast(validated: ValidatedExtraction) -> ASTNode
Converts condition dict → recursive ASTNode; raises ASTBuildError on unrecognised operators
/pipeline/conflict_detector.py — detect_conflicts(rules: list[RuleRecord]) -> list[ConflictReport]
Normalise numeric conditions to intervals; flag overlapping intervals with differing actions
Phase 4 — Orchestrator (concurrency here)
/pipeline/orchestrator.py — run_pipeline(file_path: str, doc_id: str, config: AppConfig, llm: LLMClient, db: DBConnector) -> list[RuleRecord]
Composes steps 8–14 in sequence
Applies asyncio.Semaphore(config.concurrency.max_parallel_clauses) around LLM calls
Uses asyncio.gather for parallel clause extraction
On ValidationError: retry once with a narrower prompt; if still failing, mark confidence=0 and continue
Phase 5 — Execution Engine
/engine/evaluator.py — evaluate_node(node: ASTNode, invoice: InvoiceRecord) -> bool | float
Pure recursive function; no LLM
/engine/executor.py — execute_rule(rule: RuleRecord, invoice: InvoiceRecord) -> ExecutionResult
Calls evaluator; returns decision enum + matched clause ids
Phase 6 — Notifications + Visualization
/notifications/dispatcher.py — dispatch(result: ExecutionResult, config: NotificationConfig) -> None
Dispatch only; no business logic
/visualization/graph_builder.py — build_dependency_graph(rules: list[RuleRecord]) -> GraphData
Returns serialisable graph data; no rendering
Phase 7 — API Layer
/api/schemas.py — Pydantic models for all HTTP request/response bodies
/api/dependencies.py — FastAPI Depends providers: DB session, LLM client, loaded config
/api/routes.py — three routers:
POST /upload → calls orchestrator, stores rules, returns doc_id + rule count
GET /rules/{doc_id} → fetches rules from DB
POST /execute → runs executor on invoice JSON, dispatches notifications
main.py — creates FastAPI app, includes routers, wires Langfuse middleware on startup
4. Error Handling Strategy
Layer	Error Type	Behaviour
LLM call	LLMCallError	Retry ×2 exponential backoff; re-raise with status + body
Validation	ValidationError	Retry with smaller prompt once; mark low-confidence if still failing
AST build	ASTBuildError	Raise immediately; log clause_id + bad input
DB	DBError	Raise immediately; include query params in message
Config	ConfigError	Raise at startup; crash fast before serving traffic
Circular xref	CircularReferenceError	Raise with cycle path
All errors carry: clause_id or rule_id (where applicable), doc_id, HTTP status/response (for external calls), correlation ID threaded from the API request.

5. Observability (Langfuse)
Wrap the orchestrator in a Langfuse trace at the top level; each pipeline step is a span
Each LLM call is a Langfuse generation (prompt, output, latency, model)
Retries logged as WARNING structured log entries with fields: attempt, clause_id, error_type
No PII or invoice field values logged — only IDs and structural metadata
6. Config File Structure (config.json)

llm.provider         → "nvidia" | "bedrock"
llm.model            → model name string
llm.temperature      → float
llm.max_tokens       → int
concurrency.max_parallel_clauses → int
notifications.endpoint → URL (optional)
langfuse.public_key  → read from env var, not hardcoded
langfuse.secret_key  → read from env var, not hardcoded
Secrets (API keys) come from environment variables only. config.json holds non-secret knobs. .env.example documents required env var names.

7. Docker Compose Scope
Only two services:

postgres — rules + config storage
langfuse — observability UI
FastAPI runs locally (uvicorn main:app). No worker containers.

8. Implementation Sequence Summary

Phase 1: Types → Config → DB models → DB connector → DB queries
Phase 2: LLM prompts → LLM client
Phase 3: Parser → Splitter → XRef → Extractor → Validator → Rule Builder → Conflict Detector
Phase 4: Orchestrator (wires Phase 2+3 with concurrency)
Phase 5: Evaluator → Executor
Phase 6: Notifications → Visualization
Phase 7: API schemas → API dependencies → API routes → main.py
Each phase is independently testable. No circular imports. External dependencies (LLM, DB) are injected — never imported directly inside pipeline functions.

c:\Users\jagan\Documents\coding\assesment\cashflo\docs\plans\plan1.md
UI ,fastapi ,langfuse ,postgres, everything should be running in docker compose files, so that it is easy for anyone to setup in few simple commands and it is easy to make it into production as well
Updated plan — everything containerised, single docker compose up to start.

Revised Plan: Full Docker Compose Deployment
1. What Changes vs Previous Plan
Aspect	Before	Now
FastAPI	runs locally (uvicorn on host)	runs in container
UI	not specified	runs in container
Langfuse	runs in container	runs in container (unchanged)
Postgres	runs in container	runs in container (unchanged)
Setup	multiple manual steps	docker compose up
Production path	unclear	same compose file, promoted via env overrides
2. Service Map

docker-compose.yml
  ├── ui            ← React/Next.js frontend
  ├── api           ← FastAPI app
  ├── postgres      ← rules + executions DB
  ├── langfuse-web  ← Langfuse UI + API
  ├── langfuse-worker ← Langfuse async event processor
  └── langfuse-postgres ← Langfuse's own DB (isolated from app DB)
Two Postgres instances — one for the app, one for Langfuse. Sharing a single Postgres is a hidden coupling that makes upgrades and migrations risky. Keep them separate.

3. Revised Project Directory Layout

/cashflo
  /api                    ← FastAPI source (unchanged from previous plan)
  /ui                     ← frontend source
    /src
    Dockerfile
    .env.example
  /pipeline               ← (unchanged)
  /engine                 ← (unchanged)
  /llm                    ← (unchanged)
  /db                     ← (unchanged)
  /notifications          ← (unchanged)
  /visualization          ← (unchanged)
  /config                 ← (unchanged)
  /types                  ← (unchanged)
  /infra
    /nginx                ← optional reverse proxy config for production
  main.py
  Dockerfile              ← API Dockerfile
  docker-compose.yml      ← all services, dev defaults
  docker-compose.prod.yml ← production overrides only
  .env.example            ← documents every required variable
  .env                    ← never committed; created by developer from example
  requirements.txt
4. Container Responsibilities
api container
Runs uvicorn main:app --host 0.0.0.0 --port 8000
Reads config.json mounted as a volume (so it can be changed without rebuilding)
Reads secrets from environment variables injected by Docker Compose
Depends on postgres being healthy before starting
Exposes port 8000 internally; not exposed to host in production (nginx fronts it)
ui container
Serves the frontend (React or Next.js)
In dev: runs dev server with hot reload
In prod: builds static assets, served by nginx inside the container
Communicates with api via internal Docker network using service name (http://api:8000)
Exposes port 3000 internally
postgres container
Standard postgres:16 image
Named volume for data persistence across restarts
Initialisation SQL in /docker-entrypoint-initdb.d/ for schema creation on first run
Health check: pg_isready
langfuse-web + langfuse-worker containers
Official Langfuse images
Connected to langfuse-postgres (not the app postgres)
langfuse-web exposes port 3001 internally
api container sends traces to http://langfuse-web:3000 via internal network
langfuse-postgres container
Dedicated postgres for Langfuse state
Named volume, separate from app data
Health check: pg_isready
5. Networking
Two Docker networks:

Network	Members	Purpose
app-net	ui, api, postgres, langfuse-web	app traffic
langfuse-net	langfuse-web, langfuse-worker, langfuse-postgres	Langfuse internal traffic
langfuse-web sits on both networks so api can reach it, but langfuse-postgres is not reachable from api or ui.

6. Environment Variable Strategy
All secrets and environment-specific values live in .env. The .env.example file documents every variable with a description and safe placeholder. Developers run:


cp .env.example .env
# fill in real values
docker compose up
Variables to document in .env.example:


# App DB
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

# LLM
NVIDIA_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=

# Langfuse
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_DB_PASSWORD=

# Langfuse init
NEXTAUTH_SECRET=
NEXTAUTH_URL=http://localhost:3001
SALT=

# API
LLM_PROVIDER=nvidia
config.json holds non-secret runtime knobs (model name, temperature, concurrency). It is mounted into the api container as a read-only bind mount so it can be tuned without rebuilding the image.

7. Volume Strategy
Volume	Service	Data
app-postgres-data	postgres	rules, executions, documents
langfuse-postgres-data	langfuse-postgres	Langfuse events and traces
config-volume	api (bind mount)	config.json from host
No anonymous volumes — all named so they survive docker compose down and are explicit in docker volume ls.

8. Health Checks + Startup Order

postgres           → healthcheck: pg_isready
langfuse-postgres  → healthcheck: pg_isready
langfuse-worker    → depends_on: langfuse-postgres (healthy)
langfuse-web       → depends_on: langfuse-postgres (healthy)
api                → depends_on: postgres (healthy), langfuse-web (started)
ui                 → depends_on: api (started)
depends_on with condition: service_healthy for DB dependencies. This prevents the API from crashing on startup because Postgres isn't ready.

9. Dockerfiles
API Dockerfile (multi-stage)
Stage 1 — builder: installs Python dependencies into a venv

Stage 2 — runtime: copies only the venv + source; no build tools in final image

Runs as a non-root user.

UI Dockerfile (multi-stage)
Stage 1 — builder: installs Node deps, runs build

Stage 2 — runtime (dev): runs dev server

Stage 2 — runtime (prod): copies built assets into nginx image

Runs as a non-root user.

10. Production vs Dev Difference
docker-compose.yml — dev defaults:

API container mounts source as a volume for live reload (uvicorn --reload)
UI container runs dev server with HMR
Ports exposed to host for direct access during development
docker-compose.prod.yml — production overrides only:

No source mounts; image is the artefact
UI build stage produces static assets served by nginx
restart: unless-stopped on all services
Resource limits (mem_limit, cpus) on all services
No dev ports exposed; only nginx port 80/443 exposed to host
nginx container added as reverse proxy in front of api and ui
Run prod with:


docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
11. Setup Flow (Anyone, Any Machine)

1. git clone <repo>
2. cp .env.example .env   ← fill in API keys and passwords
3. docker compose up      ← all services start, DB initialises, app ready
Access:

UI: http://localhost:3000
API docs: http://localhost:8000/docs
Langfuse: http://localhost:3001
12. Revised Implementation Sequence
Same phases as before, with two additions at the start and end:


Phase 0: Dockerfiles + docker-compose.yml + .env.example (infra first — validates all services connect)
Phase 1: Types → Config → DB models → connector → queries
Phase 2: LLM prompts → LLM client
Phase 3: Pipeline steps (parser through conflict detector)
Phase 4: Orchestrator
Phase 5: Evaluator → Executor
Phase 6: Notifications → Visualization
Phase 7: API schemas → dependencies → routes → main.py
Phase 8: UI (upload form, rules viewer, execution result display)
Phase 9: docker-compose.prod.yml + nginx config
Building Phase 0 first means every subsequent phase can be validated inside containers from day one, not just before deployment.