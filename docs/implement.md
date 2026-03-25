# Implementation Plan: Auto-CV Optimizer

The project at `/home/verno/projects/personal/learn/claude-claw/auto-cv/` is a greenfield implementation — only the specification document (`docs/roadmap.md`) and a flow diagram (`docs/flow.png`) exist. The goal is to build a complete CV optimization backend that takes a CV + Job Description and returns an ATS-optimized rewritten CV with a match score.

The spec is comprehensive: FastAPI + LangGraph + PostgreSQL + Redis + ARQ + FAISS. This plan organizes implementation into 13 ordered phases, maximizing parallelization where possible.

---

## Phase 1 — Project Skeleton

**Files:** `requirements.txt`, `.env.example`, create `backend/` directory tree.

- All dependencies pinned.
- `.env.example` lists every env var from `Settings` with defaults.

---

## Phase 2 — Foundation (parallelizable)

**Files (zero dependencies between these):**
- `backend/app/models/schemas.py` — all Pydantic models (`InputPayload`, `CVData`, `JDData`, `MatchResult`, `GenerateResult`, `JobRecord`, `JobCreateResponse`, `JobStatusResponse`)
- `backend/app/core/exceptions.py` — `CVOptimizerError`, `ParseError`, `ValidationError`, `ContextError`, `MatchError`, `RewriteError`, `JobNotFoundError`
- `backend/app/core/config.py` — `Settings` class with all env vars (LLM provider, API keys, DB URL, Redis URL, limits, context_providers)
- `backend/app/core/llm_factory.py` — `LLMFactory.create()` returning `BaseChatModel`

**Verification:** `pip install -r requirements.txt` succeeds. All imports resolve.

---

## Phase 3 — Repository Pattern

**Files:** `backend/app/repositories/job_repository.py`
- `AbstractJobRepository` (ABC) with `save`, `get`, `update_status` methods
- `InMemoryJobRepository` (for tests — no DB)
- `PostgresJobRepository` (SQLAlchemy 2.0 async, for production)

**Verification:** Unit tests use `InMemoryJobRepository` fixture, no DB needed.

---

## Phase 4 — Parser Service (pdf/docx/text parsers parallelizable)

**Files:**
- `backend/app/services/parser/base.py` — `ParserStrategy` Protocol
- `backend/app/services/parser/pdf_parser.py` — PyMuPDF
- `backend/app/services/parser/docx_parser.py` — python-docx
- `backend/app/services/parser/text_parser.py` — built-in decode
- `backend/app/services/parser/__init__.py` — `ParserService` with auto-registry by MIME + extension

**Verification:** `parse_text()` identity, `parse_file()` detects format correctly, unsupported format raises `ParseError` with 422.

---

## Phase 5 — Context Providers (all 4 providers parallelizable)

**Files:**
- `backend/app/services/context/base.py` — `ContextChunk`, `KnowledgeDoc`, `ContextProvider` Protocol
- `backend/app/services/context/markdown_provider.py` — loads `.md` files as `KnowledgeDoc` with `to_anthropic_block()` / `to_text_section()`
- `backend/app/services/context/faiss_provider.py` — FAISS index build/load/gather, persists to `data/faiss.index` + `data/faiss_docs.pkl`
- `backend/app/services/context/db_provider.py` — past successful rewrites (stub: returns `[]` until enabled)
- `backend/app/services/context/http_provider.py` — external API caller
- `backend/app/services/context/__init__.py` — `ContextRegistry` with lazy factory init (critical: no import-time API key failures)

**Verification:** `ContextRegistry.__init__` does NOT call provider factories at import time. Providers instantiated only inside `__init__`.

---

## Phase 6 — Knowledge Files (all parallel, no code)

**Files:** Drop-in `.md` files consumed by `MarkdownDocProvider`:
- `backend/app/knowledge/skills/backend.md`
- `backend/app/knowledge/skills/frontend.md`
- `backend/app/knowledge/skills/devops.md`
- `backend/app/knowledge/skills/data_science.md`
- `backend/app/knowledge/ats_keywords.md`
- `backend/app/knowledge/cv_style_guide.md`

**Verification:** `MarkdownDocProvider.gather()` returns all docs as `KnowledgeDoc` list.

---

## Phase 7 — Agents: State + All Nodes (nodes parallelizable except match_node)

**Files:**
- `backend/app/agents/state.py` — `WorkflowState` TypedDict
- `backend/app/agents/nodes/parse_node.py` — resolves parser, calls LLM for structured `CVData`/`JDData` JSON
- `backend/app/agents/nodes/validate_node.py` — Pydantic validation of `CVData`/`JDData`, routes errors to `END`
- `backend/app/agents/nodes/context_node.py` — calls `ContextRegistry.gather_docs()` + `gather_chunks()`
- `backend/app/agents/nodes/match_node.py` — calls `MatcherService`
- `backend/app/agents/nodes/rewrite_node.py` — builds Anthropic multi-block message (document blocks + text), falls back to inline text for non-Anthropic
- `backend/app/agents/nodes/format_node.py` — assembles `GenerateResult`
- `backend/app/agents/workflow.py` — `build_workflow()`: parse → validate → context → match → rewrite → format → END

**Verification:** Full workflow with mocked LLM produces valid `GenerateResult`. Error in `validate_node` routes to `END`.

---

## Phase 8 — Matcher Service

**Files:** `backend/app/services/matcher.py`
- Skill matching with synonym expansion from knowledge docs
- Score calculation (0–100)
- LLM-powered suggestions (with markdown fence stripping + `[]` fallback on parse error)

**Verification:** Score bounds, synonym expansion, missing skills detection, graceful fallback on suggestion parse error.

---

## Phase 9 — Worker

**Files:**
- `backend/app/workers/arq_settings.py` — `WorkerSettings` with functions, `redis_settings`, `max_jobs`, `job_timeout`
- `backend/app/workers/cv_worker.py` — `process_cv_job()` (workflow invoke + status updates), `enqueue_cv_job()` (receives shared `ArqRedis` pool, not a new one)

**Verification:** `enqueue_cv_job` receives pool as parameter. Status transitions: `pending` → `processing` → `done`/`failed`. `job_id` in every log line.

---

## Phase 10 — API Layer (routes + middleware parallelizable)

**Files:**
- `backend/app/core/dependencies.py` — `get_job_repository`, `get_redis` (reads `app.state.redis`)
- `backend/app/api/v1/middleware/exception_handler.py` — domain error → HTTP status mapping
- `backend/app/api/v1/middleware/auth.py` — (stub for now)
- `backend/app/api/v1/middleware/rate_limit.py` — (stub for now)
- `backend/app/api/v1/routes/health.py` — `GET /health`
- `backend/app/api/v1/routes/jobs.py` — `POST /jobs` (202 + enqueue), `GET /jobs/{job_id}`
- `backend/app/api/v1/routes/admin.py` — `POST /admin/faiss/build` (background rebuild)
- `backend/app/api/v1/router.py` — combines all routes under `/api/v1/`

**Verification:** `POST /` returns 202 with `job_id`, never blocks. File validation before enqueue. `GET /{job_id}` returns 404 for unknown jobs.

---

## Phase 11 — App Wiring

**Files:** `backend/app/main.py`
- FastAPI lifespan: Redis pool created once → stored in `app.state.redis`
- FAISS index `load_persisted()` on startup
- Clean Redis pool close on shutdown
- Router included at `/api/v1/`

**Verification:** `TestClient` lifespan test confirms pool stored and closed correctly.

---

## Phase 12 — Tests

**Files:** `backend/tests/conftest.py` + unit tests for each phase (written alongside their phase, not lumped at the end)
- `repo()` fixture → `InMemoryJobRepository`
- `mock_llm()` fixture → `AsyncMock` with pre-programmed responses
- Integration tests with `TestClient`

**Verification:** All unit tests pass without real DB/Redis/LLM.

---

## Phase 13 — Docker

**Files:** `backend/Dockerfile`, `backend/docker-compose.yml`
- API + worker + postgres + redis
- Postgres/redis with healthchecks
- API/worker wait for healthy services

**Verification:** `docker compose up --build` succeeds, `POST /api/v1/jobs` returns 202, worker picks up job, `GET /api/v1/jobs/{id}` returns done.

---

## Critical Integration Points (from spec)

1. **`app.state.redis`** — pool created once in `main.py` lifespan, `get_redis()` reads from there.
2. **`ContextRegistry` lazy init** — factory lambdas called only inside `__init__`, not at import.
3. **`InMemoryJobRepository` in all tests** — no DB/Redis needed for unit tests.
4. **`BaseChatModel` injection** — services accept `llm: BaseChatModel | None = None`, never instantiate concrete classes.
5. **202 return on `POST /`** — route returns immediately after enqueue, never awaits workflow.
6. **`job_id` in every log line** — structlog configured with `job_id` context.
7. **FAISS persistence** — `build()` writes `data/faiss.index` + `data/faiss_docs.pkl`; lifespan calls `load_persisted()`.
8. **ARQ `ctx["repo"]`** — worker receives repo via ARQ ctx dict, not as a global.

---

## Verification Plan Summary

1. **Phase 2:** `python -c "from app.core.config import settings; print(settings.llm_provider)"` resolves.
2. **Phase 3:** `repo` fixture tests pass without DB.
3. **Phase 4:** `ParserService().parse_file(b"data", "resume.pdf")` raises `ParseError`.
4. **Phase 5:** `ContextRegistry()` succeeds with no API keys set.
5. **Phase 7:** Mock LLM workflow test passes end-to-end.
6. **Phase 9:** `TestClient` API tests return 202 on `POST`, 404 on unknown job.
7. **Phase 11:** Real Redis pool connects on startup, closed on shutdown.
8. **Phase 13:** `docker compose up --build` succeeds.
