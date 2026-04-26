# CashFlo — Policy-to-Rule Engine

Extracts structured, executable rules from procurement policy PDFs and evaluates them against invoices.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/install/) v2+
- An NVIDIA NIM API key **or** AWS credentials for Bedrock

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set the following:

| Variable | Description |
|---|---|
| `POSTGRES_USER` | App database username |
| `POSTGRES_PASSWORD` | App database password |
| `POSTGRES_DB` | App database name |
| `LLM_PROVIDER` | `nvidia` or `bedrock` |
| `NVIDIA_API_KEY` | Required when `LLM_PROVIDER=nvidia` |
| `AWS_ACCESS_KEY_ID` | Required when `LLM_PROVIDER=bedrock` |
| `AWS_SECRET_ACCESS_KEY` | Required when `LLM_PROVIDER=bedrock` |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `LANGFUSE_DB_PASSWORD` | Password for Langfuse's internal database |
| `NEXTAUTH_SECRET` | Random secret for Langfuse auth — `openssl rand -base64 32` |
| `SALT` | Hashing salt for Langfuse — `openssl rand -base64 32` |
| `LANGFUSE_PUBLIC_KEY` | Generated from Langfuse UI after first start (see below) |
| `LANGFUSE_SECRET_KEY` | Generated from Langfuse UI after first start (see below) |

### Generating `NEXTAUTH_SECRET` and `SALT`

Both values must be strong random strings. Generate them before the first `docker compose up`:

**macOS / Linux**
```bash
openssl rand -base64 32   # run once for NEXTAUTH_SECRET, once for SALT
```

**Windows (PowerShell)**
```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Maximum 256) }))
```

Run each command twice — paste the first output as `NEXTAUTH_SECRET` and the second as `SALT` in your `.env`.

### Non-secret runtime config

LLM model, temperature, and concurrency settings live in [`config.json`](config.json) — edit that file directly, no rebuild needed.

---

## Development

### 1. Start all services

```bash
docker compose up
```

This starts: `postgres`, `langfuse-postgres`, `langfuse-web`, `langfuse-worker`, `api`, `ui`.

- UI → [http://localhost:3000](http://localhost:3000)
- API docs → [http://localhost:8000/docs](http://localhost:8000/docs)
- Langfuse → [http://localhost:3001](http://localhost:3001)

### 2. Generate Langfuse API keys (first time only)

1. Open [http://localhost:3001](http://localhost:3001)
2. Create an account → create an organisation → create a project
3. Go to **Settings → API Keys** → create a key pair
4. Copy `Public Key` and `Secret Key` into your `.env` as `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
5. Restart the api container to pick up the new keys:

```bash
docker compose restart api
```

### 3. Code changes

The API and UI source directories are volume-mounted into their containers:

- Changes to any Python file under `cashflo/` are picked up immediately — uvicorn runs with `--reload`.
- Changes to any file under `ui/src/` are picked up immediately — Next.js runs with HMR.

No rebuild required during development.

### 4. Rebuild after dependency changes

If you add a package to `requirements.txt` or `ui/package.json`:

```bash
docker compose up --build
```

---

## Production

### 1. Set environment variables

Use the same `.env` setup as development. Additionally set:

```bash
NEXTAUTH_URL=https://your-langfuse-domain.com
```

### 2. Start all services with production overrides

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Production differences vs dev:

- `--reload` is disabled on the API
- Source directories are **not** volume-mounted — the image is the artefact
- All services have `restart: unless-stopped`
- Memory and CPU limits are enforced
- `api` and `ui` ports are not exposed to the host
- An `nginx` container fronts all traffic on port 80

Access:

- UI + API → [http://localhost](http://localhost) (via nginx)
- Langfuse → configure a separate domain or expose port 3001 via nginx

### 3. Stop services

```bash
# Dev
docker compose down

# Prod
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

To also delete all stored data (database volumes):

```bash
docker compose down -v
```

---

## Project Layout

```
cashflo/
  api/            FastAPI routers, schemas, dependency injection
  pipeline/       PDF → clauses → LLM extraction → AST rules
  engine/         Rule executor and AST evaluator
  llm/            LLM client (NVIDIA / Bedrock) and prompt templates
  db/             SQLAlchemy models, connector, query functions
  notifications/  Deviation dispatcher
  visualization/  Rule dependency graph builder
  config/         Config loader and types
  types/          All shared named types
  ui/             Next.js frontend
  infra/nginx/    Reverse proxy config (production)
  main.py         FastAPI app entry point
  config.json     Non-secret runtime knobs
  docker-compose.yml       Dev defaults
  docker-compose.prod.yml  Production overrides
  .env.example    Documents every required environment variable
```
