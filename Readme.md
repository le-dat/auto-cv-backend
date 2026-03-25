# CV Optimizer

Backend service that rewrites a CV to better match a Job Description, producing an ATS-optimized resume and a match score.

## Stack

| Layer | Library |
|---|---|
| API | FastAPI (async) |
| Workflow | LangGraph (multi-agent state machine) |
| LLM | OpenAI / Groq / Anthropic (switchable via factory) |
| Vector store | FAISS (faiss-cpu) |
| Parsers | PyMuPDF (PDF), python-docx (DOCX), built-in (text) |
| Job queue | ARQ (Redis-backed) |
| Database | PostgreSQL + asyncpg |
| ORM | SQLAlchemy 2.0 async |
| Schema | Pydantic v2 |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your API keys

# 3. Start infrastructure (Redis + Postgres)
docker compose -f backend/docker-compose.yml up postgres redis -d

# 4. Run the API server
uvicorn backend.app.main:app --reload

# 5. In another terminal, start the worker
arq backend.app.workers.arq_settings.WorkerSettings
```

## API

### Submit a job

```bash
# File upload
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "cv_file=@my_cv.pdf" \
  -F "jd_file=@jd.docx"

# Plain text
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "cv_text=John Doe, Python engineer..." \
  -F "jd_text=We are looking for a senior backend..."

# Mixed (file CV + text JD)
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "cv_file=@my_cv.pdf" \
  -F "jd_text=We are looking for a senior backend..."
```

Returns `202 Accepted` with a `job_id`.

### Poll for result

```bash
curl http://localhost:8000/api/v1/jobs/<job_id>
```

### Health check

```bash
curl http://localhost:8000/api/v1/health
```

### Rebuild FAISS index (after processing completed jobs)

```bash
curl -X POST http://localhost:8000/api/v1/admin/faiss/build
```

## Architecture

```
POST /api/v1/jobs (202)
  → enqueue → ARQ worker
                  → parse_node      (extract CV/JD as structured JSON)
                  → validate_node   (guard against bad LLM output)
                  → context_node    (load knowledge docs + FAISS/DB chunks)
                  → match_node     (skill matching + ATS keyword scoring)
                  → rewrite_node   (rewrite CV using Anthropic document blocks)
                  → format_node    (assemble GenerateResult)

Poll GET /api/v1/jobs/{id} → done + cv_markdown + match_score
```

## Adding new components

### New input format (e.g. RTF)
1. Create `backend/app/services/parser/rtf_parser.py` implementing `ParserStrategy`
2. Append to `_registry` in `backend/app/services/parser/__init__.py`
3. Add `"rtf"` to `ALLOWED_INPUT_TYPES` in `.env`

### New context provider
1. Create `backend/app/services/context/my_provider.py` implementing `ContextProvider`
2. Add entry to `_PROVIDER_FACTORIES` in `backend/app/services/context/__init__.py`
3. Add name to `CONTEXT_PROVIDERS` in `.env`

### New knowledge file
Drop a `.md` file into `backend/app/knowledge/` — `MarkdownDocProvider` picks it up on next startup, no code change needed.

## Project structure

```
backend/
├── app/
│   ├── api/v1/routes/       # jobs.py, admin.py, health.py
│   ├── agents/nodes/        # parse, validate, context, match, rewrite, format
│   ├── core/                # config, llm_factory, exceptions, dependencies
│   ├── models/schemas.py    # Pydantic models
│   ├── repositories/       # job_repository (ABC + InMemory + Postgres)
│   ├── services/
│   │   ├── parser/         # PDF, DOCX, text parsers + registry
│   │   ├── context/         # FAISS, DB, HTTP, Markdown providers
│   │   └── matcher.py       # skill matching + scoring
│   ├── knowledge/           # .md skill/style guides
│   ├── workers/            # ARQ worker + settings
│   └── main.py              # FastAPI app + lifespan
├── tests/
├── Dockerfile
└── docker-compose.yml
```

## Environment variables

See `.env.example`. Key variables:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai`, `groq`, or `claude` |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL DSN |
| `REDIS_URL` | `redis://localhost:6379` | Redis DSN |
| `CONTEXT_PROVIDERS` | `markdown,faiss` | Active context providers |
| `MAX_CONCURRENT_JOBS` | `5` | ARQ worker concurrency |
