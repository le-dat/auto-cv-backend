# CV Optimizer — Backend Spec

**Goal**: text/PDF/DOCX(JD) + text/PDF/DOCX(CV) → rewritten CV optimized for JD + match report.
**Flow**: `POST /api/v1/jobs` (202) → poll `GET /api/v1/jobs/{id}` → done.

> ⚠️ Never fabricate experience, skills, or achievements not in original CV.
> ⚠️ All routes prefixed `/api/v1/` from day one — no versioning = breaking changes.
> ⚠️ Never commit `.env` — use `.env.example` only.

---

## Stack

| Layer | Library | Notes |
|---|---|---|
| API | FastAPI | async, OpenAPI auto-docs |
| Workflow | LangGraph | multi-agent state machine |
| LLM abstraction | LangChain `BaseChatModel` | never use concrete class directly |
| LLM providers | OpenAI / Groq / Anthropic | switched via factory |
| Embeddings | `text-embedding-3-small` | cost-effective |
| Vector store | faiss-cpu | local first |
| PDF | PyMuPDF (fitz) | fast + accurate |
| DOCX | python-docx | via parser strategy |
| Plain text | built-in | via parser strategy |
| Schema | Pydantic v2 | runtime + static |
| Settings | pydantic-settings | `.env` loader |
| Job queue | ARQ | async-native, Redis-backed — **required** |
| DB | PostgreSQL + asyncpg | job + result persistence — **required** |
| ORM | SQLAlchemy 2.0 async | repository pattern |
| Cache | Redis | job status, embedding cache — **required** |
| Logging | structlog | structured JSON, keyed by `job_id` |
| Testing | pytest + pytest-asyncio | unit + integration |

> ⚠️ PostgreSQL + Redis are **not optional** — without them you lose job persistence across restarts, can't scale workers, and can't implement past-CV memory.

---

## Project Structure

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── routes/
│   │   │   ├── jobs.py
│   │   │   ├── admin.py         # FAISS rebuild trigger + internal ops
│   │   │   └── health.py
│   │   ├── router.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       ├── rate_limit.py
│   │       └── exception_handler.py
│   ├── agents/
│   │   ├── state.py
│   │   ├── workflow.py
│   │   └── nodes/
│   │       ├── parse_node.py
│   │       ├── validate_node.py
│   │       ├── context_node.py      # ← fetches from all registered providers
│   │       ├── match_node.py
│   │       ├── rewrite_node.py
│   │       └── format_node.py
│   ├── core/
│   │   ├── config.py
│   │   ├── llm_factory.py
│   │   ├── exceptions.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── schemas.py
│   │   └── db_models.py
│   ├── repositories/
│   │   └── job_repository.py
│   ├── services/
│   │   ├── parser/
│   │   │   ├── __init__.py          # ParserService + auto-registry
│   │   │   ├── base.py              # ParserStrategy Protocol
│   │   │   ├── pdf_parser.py
│   │   │   ├── docx_parser.py
│   │   │   └── text_parser.py
│   │   ├── context/                 # ← extensible inference context
│   │   │   ├── __init__.py          # ContextRegistry
│   │   │   ├── base.py              # ContextProvider Protocol + ContextChunk + KnowledgeDoc
│   │   │   ├── faiss_provider.py    # vector similarity (past CVs/JDs)
│   │   │   ├── db_provider.py       # past successful rewrites from PostgreSQL
│   │   │   ├── markdown_provider.py # .md skill docs → Anthropic document blocks
│   │   │   └── http_provider.py     # external API (optional)
│   │   ├── matcher.py
│   │   └── rewriter.py
│   ├── knowledge/                   # ← internal .md files — Claude reads natively as documents
│   │   ├── skills/
│   │   │   ├── backend.md           # Python, FastAPI, databases, cloud
│   │   │   ├── frontend.md          # React, Vue, CSS, accessibility
│   │   │   ├── devops.md            # Docker, K8s, CI/CD, monitoring
│   │   │   └── data_science.md      # ML, feature engineering, experimentation
│   │   ├── ats_keywords.md          # ATS keyword rules by industry
│   │   └── cv_style_guide.md        # rewriting rules, tone, bullet patterns
│   ├── workers/
│   │   ├── cv_worker.py
│   │   └── arq_settings.py
│   └── main.py                  # FastAPI lifespan: Redis pool + FAISS load on startup
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Core Patterns

### 1. Settings — `core/config.py`

> ⚠️ Never read `.env` directly in services. All config goes through `settings`.
> ⚠️ `context_providers` controls which providers are active — add/remove a provider by editing `.env` only, zero code change.

```python
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # LLM
    llm_provider: Literal["openai", "groq", "claude"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama3-70b-8192"
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"

    # Infrastructure
    database_url: str = "postgresql+asyncpg://user:pass@localhost/cvoptimizer"
    redis_url: str = "redis://localhost:6379"

    # Input — extend by adding to allowed_input_types
    max_file_size_mb: int = 10
    allowed_input_types: list[str] = ["pdf", "docx", "txt", "text", "md"]

    # Context providers — resolved in order, all active providers contribute chunks
    # Enable:  add name to list.  Disable: remove name.  No code change needed.
    context_providers: list[str] = ["markdown", "faiss"]
    context_top_k: int = 5                        # chunks fetched per dynamic provider
    # Markdown knowledge docs — passed to Claude as document blocks (not chunked)
    knowledge_dir: str = "app/knowledge"          # all .md files scanned recursively
    knowledge_max_docs: int = 10                  # cap on docs injected per request
    db_context_enabled: bool = False              # enable when past-job data exists
    http_context_url: str = ""                    # optional external enrichment API

    # Limits
    max_concurrent_jobs: int = 5
    job_timeout_seconds: int = 120
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

### 2. LLM Factory — `core/llm_factory.py`

> ⚠️ Every service takes `BaseChatModel` — never a concrete class. Enables mock injection in tests.

```python
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from app.core.config import settings

class LLMFactory:
    @staticmethod
    def create(provider: str | None = None) -> BaseChatModel:
        provider = provider or settings.llm_provider
        match provider:
            case "openai":  return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0.3)
            case "groq":    return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=0.3)
            case "claude":  return ChatAnthropic(model=settings.claude_model, api_key=settings.anthropic_api_key, temperature=0.3)
            case _: raise ValueError(f"Unknown LLM provider: {provider}")
```

---

### 3. Custom Exceptions — `core/exceptions.py`

> ⚠️ Map domain errors to HTTP codes in middleware — never raise `HTTPException` inside services.

```python
class CVOptimizerError(Exception): pass
class ParseError(CVOptimizerError): pass
class ValidationError(CVOptimizerError): pass
class ContextError(CVOptimizerError): pass
class MatchError(CVOptimizerError): pass
class RewriteError(CVOptimizerError): pass
class JobNotFoundError(CVOptimizerError): pass
```

```python
# api/middleware/exception_handler.py
async def cv_optimizer_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    status_map = {ParseError: 422, ValidationError: 422, JobNotFoundError: 404, ContextError: 500}
    return JSONResponse(status_code=status_map.get(type(exc), 500), content={"error": str(exc)})
```

---

### 4. Repository Pattern — `repositories/job_repository.py`

> ⚠️ Services never import SQLAlchemy. `InMemoryJobRepository` used in all tests — no DB needed.

```python
from abc import ABC, abstractmethod
from app.models.schemas import JobRecord

class AbstractJobRepository(ABC):
    @abstractmethod
    async def save(self, job: JobRecord) -> str: ...
    @abstractmethod
    async def get(self, job_id: str) -> JobRecord | None: ...
    @abstractmethod
    async def update_status(self, job_id: str, status: str, result: dict | None = None, error: str | None = None) -> None: ...

class InMemoryJobRepository(AbstractJobRepository):
    """Use in tests — no DB required."""
    def __init__(self): self._store: dict[str, JobRecord] = {}
    async def save(self, job): self._store[job.id] = job; return job.id
    async def get(self, job_id): return self._store.get(job_id)
    async def update_status(self, job_id, status, result=None, error=None):
        if j := self._store.get(job_id):
            j.status = status; j.result = result; j.error = error

class PostgresJobRepository(AbstractJobRepository):
    def __init__(self, db_session): self.db = db_session
    async def save(self, job): ...
    async def get(self, job_id): ...
    async def update_status(self, job_id, status, result=None, error=None): ...
```

---

## Input Handling — `services/parser/`

**Design**: every format is a `ParserStrategy`. `ParserService` auto-detects format from MIME type or extension. API accepts either file upload or raw text string — both paths resolve to plain text before entering the workflow.

> ⚠️ Detection order: MIME type → file extension → raise `ParseError` with 422.
> ⚠️ To add a new format: create one class + add to `_registry`. No other files change.

### `services/parser/base.py`

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ParserStrategy(Protocol):
    media_types: list[str]   # MIME types this parser handles
    extensions: list[str]    # file extensions (without dot)

    async def extract_text(self, raw: bytes) -> str: ...
```

### Strategies

```python
# services/parser/pdf_parser.py
class PDFParser:
    media_types = ["application/pdf"]
    extensions  = ["pdf"]

    async def extract_text(self, raw: bytes) -> str:
        import fitz
        doc = fitz.open(stream=raw, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)


# services/parser/docx_parser.py
class DocxParser:
    media_types = ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    extensions  = ["docx"]

    async def extract_text(self, raw: bytes) -> str:
        import docx, io
        return "\n".join(p.text for p in docx.Document(io.BytesIO(raw)).paragraphs if p.text.strip())


# services/parser/text_parser.py
class TextParser:
    media_types = ["text/plain", "text/markdown"]
    extensions  = ["txt", "text", "md"]

    async def extract_text(self, raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace").strip()
```

### `services/parser/__init__.py`

```python
from app.services.parser.pdf_parser  import PDFParser
from app.services.parser.docx_parser import DocxParser
from app.services.parser.text_parser import TextParser
from app.core.exceptions import ParseError

# Add new format: instantiate + append here. Zero other changes needed.
_registry: list = [PDFParser(), DocxParser(), TextParser()]

_by_mime = {m: p for p in _registry for m in p.media_types}
_by_ext  = {e: p for p in _registry for e in p.extensions}


class ParserService:
    async def parse_file(self, raw: bytes, filename: str, content_type: str | None = None) -> str:
        """Resolve parser from MIME type first, then file extension."""
        parser = _by_mime.get(content_type or "") or _by_ext.get(filename.rsplit(".", 1)[-1].lower())
        if not parser:
            raise ParseError(f"Unsupported input: content_type={content_type}, file={filename}")
        return await parser.extract_text(raw)

    async def parse_text(self, text: str) -> str:
        """Direct text input — no parsing needed."""
        return text.strip()
```

---

## Extensible Inference Context — `services/context/`

**Problem**: LLM rewrite quality improves with relevant context — past successful CVs, skill taxonomies, industry keywords, role templates. This context must be pluggable and configurable without touching workflow code.

**Design**: `ContextProvider` protocol + `ContextRegistry`. `context_node` calls `registry.gather(query)` → all active providers return `ContextChunk` list → chunks stored in `WorkflowState.context_chunks` → consumed by `match_node` and `rewrite_node`.

```
context_node
  └─ ContextRegistry.gather(query)
        ├─ FAISSContextProvider    → top-k similar past CVs / JDs  [enabled: always]
        ├─ StaticContextProvider   → skill_taxonomy, industry_keywords, cv_templates  [enabled: always]
        ├─ DBContextProvider       → past successful rewrites from PostgreSQL  [disabled until data exists]
        └─ HTTPContextProvider     → external enrichment API  [disabled until URL set]
```

### `services/context/base.py`

```python
from typing import Protocol, runtime_checkable, Any
from dataclasses import dataclass, field

@dataclass
class ContextChunk:
    """Dynamic context — retrieved at runtime (FAISS, DB, HTTP)."""
    content: str
    source: str           # provider name — for logging and prompt attribution
    score: float = 1.0    # relevance 0–1; used to rank and deduplicate

@dataclass
class KnowledgeDoc:
    """
    Static internal .md file — passed directly to Claude as a document block.
    Claude reads the full file with its markdown structure intact (headings, lists, tables).
    For non-Anthropic providers, content is prepended to the prompt as a text section.
    """
    title: str            # shown to Claude as the document title
    content: str          # raw markdown — never chunked
    filename: str         # e.g. "skills/backend.md" — for logging
    context_hint: str     # tells Claude how to use this doc in its reply
    always_include: bool = True   # if True, included regardless of query relevance

    def to_anthropic_block(self) -> dict[str, Any]:
        """Serialize to Anthropic document content block."""
        return {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": self.content},
            "title": self.title,
            "context": self.context_hint,
            "citations": {"enabled": False},
        }

    def to_text_section(self) -> str:
        """Fallback for non-Anthropic providers — inline as a prompt section."""
        return f"## Reference: {self.title}\n\n{self.content}\n"


@runtime_checkable
class ContextProvider(Protocol):
    name: str

    async def is_ready(self) -> bool: ...
    async def gather(self, query: str, top_k: int) -> list[ContextChunk]: ...
```

### `services/context/__init__.py`

> ⚠️ To add a dynamic provider: implement `ContextProvider`, add to `_all_providers`, add name to `.env`. Zero workflow changes.
> ⚠️ `KnowledgeDoc` (from `MarkdownDocProvider`) goes to `state["knowledge_docs"]` — separate from `state["context_chunks"]`. Never mixed.
> ⚠️ Providers returning `is_ready() = False` are skipped silently — no crash when data doesn't exist yet.
> ⚠️ **Lazy init**: providers are instantiated inside `ContextRegistry.__init__`, not at module import time. This prevents import failures when API keys are absent (CI, test env).

```python
import structlog
from app.core.config import settings
from app.services.context.base import ContextChunk, KnowledgeDoc
from app.services.context.faiss_provider    import FAISSContextProvider
from app.services.context.markdown_provider import MarkdownDocProvider
from app.services.context.db_provider       import DBContextProvider
from app.services.context.http_provider     import HTTPContextProvider

log = structlog.get_logger()

# Provider factory map — providers are instantiated lazily inside ContextRegistry,
# NOT at module import time. This avoids failures when API keys are absent (CI, tests).
_PROVIDER_FACTORIES = {
    "faiss": lambda: FAISSContextProvider(),
    "db":    lambda: DBContextProvider(),
    "http":  lambda: HTTPContextProvider(settings.http_context_url),
}


class ContextRegistry:
    def __init__(self):
        # Instantiate only active providers — avoids OpenAI/HTTP client init when not needed.
        self._active: list = [
            _PROVIDER_FACTORIES[name]()
            for name in settings.context_providers
            if name in _PROVIDER_FACTORIES
        ]
        self._markdown = MarkdownDocProvider(settings.knowledge_dir)
        # Expose faiss provider for build trigger (startup / admin endpoint)
        self.faiss: FAISSContextProvider | None = next(
            (p for p in self._active if isinstance(p, FAISSContextProvider)), None
        )

    async def gather_docs(self, query: str) -> list[KnowledgeDoc]:
        """Load .md knowledge files. Always called regardless of context_providers setting."""
        if not await self._markdown.is_ready():
            log.warning("context.markdown.not_ready"); return []
        docs = await self._markdown.gather(query, top_k=settings.knowledge_max_docs)
        log.info("context.docs.loaded", count=len(docs), files=[d.filename for d in docs])
        return docs

    async def gather_chunks(self, query: str) -> list[ContextChunk]:
        chunks: list[ContextChunk] = []
        for provider in self._active:
            if not await provider.is_ready():
                log.debug("context.provider.skipped", provider=provider.name); continue
            try:
                results = await provider.gather(query, top_k=settings.context_top_k)
                chunks.extend(results)
                log.debug("context.provider.ok", provider=provider.name, chunks=len(results))
            except Exception as e:
                log.warning("context.provider.error", provider=provider.name, error=str(e))
        # Deduplicate by content hash, sort by relevance score
        seen, deduped = set(), []
        for c in sorted(chunks, key=lambda x: x.score, reverse=True):
            h = hash(c.content[:120])
            if h not in seen: seen.add(h); deduped.append(c)
        return deduped


context_registry = ContextRegistry()
```

### Built-in Providers

```python
# services/context/faiss_provider.py
# Stores embeddings of past CVs + JDs. Nearest matches fetched at inference time.
# build() is called once on startup (via lifespan hook) and again via POST /api/v1/admin/faiss/build.
import numpy as np, faiss, pathlib, pickle
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from app.services.context.base import ContextChunk

INDEX_PATH = pathlib.Path("data/faiss.index")
DOCS_PATH  = pathlib.Path("data/faiss_docs.pkl")

class FAISSContextProvider:
    name = "faiss"
    def __init__(self):
        # OpenAIEmbeddings is instantiated here (inside ContextRegistry lazy init),
        # NOT at module import time — safe when OPENAI_API_KEY is absent.
        self._emb = OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)
        self._index: faiss.IndexFlatL2 | None = None
        self._docs: list[str] = []

    async def is_ready(self) -> bool: return self._index is not None and len(self._docs) > 0

    async def load_persisted(self) -> bool:
        """Load pre-built index from disk on startup. Returns True if successful."""
        if INDEX_PATH.exists() and DOCS_PATH.exists():
            self._index = faiss.read_index(str(INDEX_PATH))
            self._docs  = pickle.loads(DOCS_PATH.read_bytes())
            return True
        return False

    async def build(self, documents: list[str]) -> None:
        """Build index from documents and persist to disk."""
        vectors = await self._emb.aembed_documents(documents)
        self._index = faiss.IndexFlatL2(len(vectors[0]))
        self._index.add(np.array(vectors, dtype=np.float32))
        self._docs = documents
        # Persist so next restart skips rebuild
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(INDEX_PATH))
        DOCS_PATH.write_bytes(pickle.dumps(self._docs))

    async def gather(self, query: str, top_k: int) -> list[ContextChunk]:
        v = await self._emb.aembed_query(query)
        D, I = self._index.search(np.array([v], dtype=np.float32), top_k)
        return [ContextChunk(content=self._docs[i], source="faiss", score=float(1/(1+D[0][n])))
                for n, i in enumerate(I[0]) if i < len(self._docs)]
```

```python
# services/context/markdown_provider.py
# Loads all .md files from knowledge/ dir on startup.
# Passes them as KnowledgeDoc — NOT chunked. Claude reads each file whole.
# To add internal knowledge: drop a .md file into app/knowledge/ — zero code change.
import pathlib
from app.services.context.base import KnowledgeDoc

# Metadata table: maps filename pattern → context_hint for Claude
# Add entries here when adding new .md files with specific usage intent.
_HINTS: dict[str, str] = {
    "backend":      "Use this to evaluate and standardize backend skill descriptions.",
    "frontend":     "Use this to evaluate and standardize frontend skill descriptions.",
    "devops":       "Use this to evaluate and standardize DevOps skill descriptions.",
    "data_science": "Use this to evaluate and standardize data science skill descriptions.",
    "ats_keywords": "Use the ATS keywords listed here to optimize the CV for applicant tracking systems.",
    "cv_style":     "Follow these style rules strictly when rewriting the CV.",
}
_DEFAULT_HINT = "Use this reference document to improve the accuracy of your response."


class MarkdownDocProvider:
    name = "markdown"

    def __init__(self, knowledge_dir: str):
        self._dir = pathlib.Path(knowledge_dir)
        self._docs: list[KnowledgeDoc] = []
        self._loaded = False

    async def is_ready(self) -> bool:
        if not self._loaded: await self._load()
        return len(self._docs) > 0

    async def _load(self) -> None:
        self._docs = []
        for f in sorted(self._dir.rglob("*.md")):
            content = f.read_text(encoding="utf-8").strip()
            if not content: continue
            # Extract title from first H1 line, fall back to filename stem
            first_line = content.splitlines()[0]
            title = first_line.lstrip("# ").strip() if first_line.startswith("#") else f.stem.replace("_", " ").title()
            hint_key = next((k for k in _HINTS if k in f.stem.lower()), None)
            self._docs.append(KnowledgeDoc(
                title=title,
                content=content,
                filename=str(f.relative_to(self._dir)),
                context_hint=_HINTS.get(hint_key, _DEFAULT_HINT),
                always_include=True,
            ))
        self._loaded = True

    async def gather(self, query: str, top_k: int) -> list[KnowledgeDoc]:
        # always_include=True → return all docs (Claude handles relevance internally)
        # For large knowledge bases: rank by keyword overlap and cap at top_k
        always = [d for d in self._docs if d.always_include]
        ranked = [d for d in self._docs if not d.always_include]
        if ranked:
            q = set(query.lower().split())
            ranked.sort(key=lambda d: len(q & set(d.content.lower().split())), reverse=True)
        return (always + ranked)[:top_k]
```

```python
# services/context/db_provider.py
# Retrieves past successful rewrites. Enabled via settings.db_context_enabled.
from app.services.context.base import ContextChunk
from app.core.config import settings

class DBContextProvider:
    name = "db"
    async def is_ready(self) -> bool: return settings.db_context_enabled
    async def gather(self, query: str, top_k: int) -> list[ContextChunk]:
        # SELECT cv_markdown, match_score FROM job_results
        # WHERE status='done' AND match_score >= 75 ORDER BY match_score DESC LIMIT top_k
        return []   # implement with SQLAlchemy session via DI
```

```python
# services/context/http_provider.py
# Calls external enrichment API (e.g. internal HR system, skills API).
# Active only when settings.http_context_url is non-empty.
import httpx
from app.services.context.base import ContextChunk
from app.core.config import settings

class HTTPContextProvider:
    name = "http"
    def __init__(self, url: str): self._url = url
    async def is_ready(self) -> bool: return bool(self._url)
    async def gather(self, query: str, top_k: int) -> list[ContextChunk]:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(self._url, json={"query": query, "top_k": top_k})
            r.raise_for_status()
            return [ContextChunk(content=i["text"], source="http", score=i.get("score", 0.5))
                    for i in r.json().get("results", [])]
```

### Internal Knowledge Files (`.md`)

> ⚠️ Files are read whole — never chunked. Claude receives each as a structured document block.
> ⚠️ To add domain knowledge: create a `.md` file in `app/knowledge/`, optionally add a hint in `_HINTS`. Zero code change.
> ⚠️ Keep each file focused on one topic. Claude handles cross-file reasoning internally.

```markdown
<!-- app/knowledge/skills/backend.md -->
# Backend Engineering Skills

## Programming Languages
- **Python** — preferred for data-heavy services, scripting, ML pipelines
- **Go** — preferred for high-throughput services, low latency APIs
- **Java / Kotlin** — common in enterprise, Spring Boot ecosystem
- **Node.js / TypeScript** — preferred for real-time, event-driven services

## Web Frameworks
- **FastAPI** — async Python API framework; modern, type-safe, OpenAPI auto-docs
- **Django** — batteries-included Python framework; strong ORM, admin panel
- **Express / NestJS** — Node.js API frameworks

## Databases
- **PostgreSQL** — standard relational DB; use for transactional data, full-text search
- **MySQL / MariaDB** — alternative relational; common in legacy stacks
- **MongoDB** — document store; use when schema is highly variable
- **Redis** — in-memory cache, pub/sub, job queues

## Synonyms & equivalences
When evaluating a CV, treat these as equivalent skills:
- Postgres = PostgreSQL
- Mongo = MongoDB
- K8s = Kubernetes
- GCP = Google Cloud Platform = Google Cloud
```

```markdown
<!-- app/knowledge/ats_keywords.md -->
# ATS Keyword Rules

## What is ATS
Applicant Tracking Systems (ATS) scan CVs for exact keyword matches before a human sees them.
Failing to include required keywords = automatic rejection, regardless of experience.

## Rules for the rewriter
1. Mirror the exact phrasing from the JD when possible (e.g. "CI/CD pipelines" not "pipeline automation")
2. Include both full name and acronym on first use (e.g. "Test-Driven Development (TDD)")
3. Place high-priority keywords in: Summary, Skills section, first bullet of most recent role
4. Never add keywords for skills the candidate does not have

## Common high-value keywords by domain
**Software engineering**: agile, scrum, CI/CD, microservices, REST API, GraphQL, unit testing, code review, system design
**Data / ML**: machine learning, feature engineering, model training, A/B testing, data pipeline, ETL, statistical analysis
**DevOps / Platform**: infrastructure as code, Terraform, Kubernetes, observability, SRE, incident response, SLA
**Management**: cross-functional, stakeholder management, roadmap, OKR, sprint planning, mentoring
```

```markdown
<!-- app/knowledge/cv_style_guide.md -->
# CV Rewriting Style Guide

## Core rules
- Every bullet point starts with a strong past-tense action verb
- Bullets follow: Action → Object → Outcome (measurable if possible)
- No pronouns ("I", "we", "my") anywhere in the CV
- No filler phrases: "responsible for", "helped with", "involved in"
- Maximum 5 bullets per role; ruthlessly cut the weakest ones

## Seniority calibration
| Level | Summary tone | Bullet verbs | Experience entries |
|---|---|---|---|
| Senior (7+ yrs) | Strategic, outcome-focused | Led, Architected, Drove, Owned, Defined | 3–4 roles |
| Mid (3–6 yrs) | Collaborative, impact-focused | Built, Implemented, Improved, Delivered | 4–5 roles |
| Junior (0–2 yrs) | Eager, learning-focused | Developed, Contributed, Assisted, Created | 2–3 roles |

## Bullet upgrade examples
❌ "Responsible for maintaining the backend API"
✅ "Maintained and extended a FastAPI backend serving 2M daily requests with 99.9% uptime"

❌ "Helped with migration to the cloud"
✅ "Co-led AWS migration of 12 microservices, reducing infrastructure costs by 30%"

## What NOT to fabricate
- Company names, team sizes, user numbers not mentioned in the original CV
- Technologies not listed anywhere in the original
- Dates, titles, or education details not present in the original
```

---

## Data Schemas — `models/schemas.py`

```python
from __future__ import annotations
from uuid import uuid4
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, EmailStr

class InputPayload(BaseModel):
    """Unified input. Exactly one of raw or text must be set."""
    raw: bytes | None = None        # file upload
    text: str | None = None         # direct text input
    filename: str = "input.txt"
    content_type: str | None = None

    def is_valid(self) -> bool: return bool(self.raw) != bool(self.text)  # XOR

class Experience(BaseModel):
    company: str; title: str; start_date: str
    end_date: str | None = None; bullets: list[str]

class Education(BaseModel):
    institution: str; degree: str; field: str
    graduation_year: int | None = None

class CVData(BaseModel):
    name: str; email: EmailStr | None = None; phone: str | None = None
    linkedin_url: str | None = None; summary: str | None = None
    skills: list[str]; experience: list[Experience]; education: list[Education]
    projects: list[str] = []; certifications: list[str] = []; languages: list[str] = []

class JDData(BaseModel):
    title: str; company_name: str | None = None; location: str | None = None
    job_type: Literal["full-time","part-time","contract","internship"] | None = None
    required_skills: list[str]; preferred_skills: list[str] = []
    responsibilities: list[str]; experience_required: str | None = None
    salary_range: str | None = None

class MatchResult(BaseModel):
    score: float = Field(ge=0, le=100)
    matching_skills: list[str]; missing_skills: list[str]
    strong_skills: list[str]; suggestions: list[str]; ats_keywords: list[str]

class GenerateResult(BaseModel):
    cv_markdown: str; match_result: MatchResult
    processing_time_ms: int; llm_model_used: str
    context_sources: list[str] = []    # which providers contributed — for auditability

class JobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["pending","processing","done","failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: GenerateResult | None = None; error: str | None = None

class JobCreateResponse(BaseModel): job_id: str; status: str; message: str

class JobStatusResponse(BaseModel):
    job_id: str; status: str; result: GenerateResult | None = None
    error: str | None = None; created_at: datetime; updated_at: datetime
```

---

## API Layer — `api/v1/routes/jobs.py`

> ⚠️ `POST /jobs` returns 202 immediately — never waits for LLM.
> ⚠️ Accepts file OR text for both CV and JD — never require file when text is sufficient.
> ⚠️ Validate format + size at API boundary before enqueuing.
> ⚠️ `redis` pool is injected via `Depends(get_redis)` — shared from lifespan, **never created per-request**.

```python
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request
from arq.connections import ArqRedis
from app.models.schemas import JobCreateResponse, JobStatusResponse, JobRecord, InputPayload
from app.repositories.job_repository import AbstractJobRepository
from app.core.dependencies import get_job_repository
from app.workers.cv_worker import enqueue_cv_job
from app.core.config import settings

router = APIRouter()
MAX_BYTES = settings.max_file_size_mb * 1024 * 1024

# Dependency: pull shared ArqRedis pool stored in app.state by lifespan.
def get_redis(request: Request) -> ArqRedis:
    return request.app.state.redis

def _make_payload(file: UploadFile | None, text: str | None, field: str) -> InputPayload:
    if file and text:  raise HTTPException(422, f"{field}: provide file OR text, not both")
    if not file and not text: raise HTTPException(422, f"{field}: file or text required")
    if text: return InputPayload(text=text, filename="input.txt", content_type="text/plain")
    return InputPayload(filename=file.filename, content_type=file.content_type)

@router.post("", response_model=JobCreateResponse, status_code=202)
async def create_job(
    cv_file: UploadFile | None = File(None),
    jd_file: UploadFile | None = File(None),
    cv_text: str | None = Form(None),
    jd_text: str | None = Form(None),
    repo: AbstractJobRepository = Depends(get_job_repository),
    redis: ArqRedis = Depends(get_redis),
):
    cv = _make_payload(cv_file, cv_text, "cv")
    jd = _make_payload(jd_file, jd_text, "jd")
    if cv_file: cv.raw = await cv_file.read()
    if jd_file: jd.raw = await jd_file.read()
    for p, name in [(cv, "cv"), (jd, "jd")]:
        if p.raw and len(p.raw) > MAX_BYTES:
            raise HTTPException(413, f"{name}_file exceeds {settings.max_file_size_mb} MB limit")
        ext = p.filename.rsplit(".", 1)[-1].lower()
        if p.raw and ext not in settings.allowed_input_types:
            raise HTTPException(422, f"Unsupported format: {ext}. Allowed: {settings.allowed_input_types}")
    job = JobRecord()
    await repo.save(job)
    await enqueue_cv_job(redis, job.id, cv, jd)  # shared pool — no new connection opened
    return JobCreateResponse(job_id=job.id, status="pending", message=f"Poll GET /api/v1/jobs/{job.id}")

@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, repo: AbstractJobRepository = Depends(get_job_repository)):
    job = await repo.get(job_id)
    if not job: raise HTTPException(404, f"Job {job_id} not found")
    return JobStatusResponse(**job.model_dump())
```

### FAISS Admin Endpoint — `api/v1/routes/admin.py`

> ⚠️ This endpoint triggers FAISS index rebuild from all completed jobs. Protect with auth middleware in production.
> ⚠️ `POST /api/v1/admin/faiss/build` returns immediately with 202 — heavy embed work runs in background.

```python
from fastapi import APIRouter, BackgroundTasks
from app.services.context import context_registry
from app.repositories.job_repository import AbstractJobRepository
from app.core.dependencies import get_job_repository
from fastapi import Depends
import structlog

log = structlog.get_logger()
admin_router = APIRouter(prefix="/admin")

@admin_router.post("/faiss/build", status_code=202)
async def rebuild_faiss_index(
    background_tasks: BackgroundTasks,
    repo: AbstractJobRepository = Depends(get_job_repository),
):
    """Rebuild FAISS index from all completed jobs. Persists to disk automatically."""
    background_tasks.add_task(_do_build, repo)
    return {"message": "FAISS rebuild started in background"}

async def _do_build(repo: AbstractJobRepository):
    if context_registry.faiss is None:
        log.warning("admin.faiss.not_configured"); return
    # Fetch all done job CVs from repository
    documents = await repo.list_done_cv_texts()   # implement: SELECT cv_text FROM job_results WHERE status='done'
    if not documents:
        log.warning("admin.faiss.no_documents"); return
    await context_registry.faiss.build(documents)
    log.info("admin.faiss.built", count=len(documents))
```

### `main.py` — FastAPI Lifespan (Redis pool + FAISS load on startup)

> ⚠️ Redis pool is created **once** in lifespan and stored in `app.state.redis` — never per-request.
> ⚠️ On startup, FAISS tries to load a persisted index from disk. If none exists, it stays `is_ready=False` until `POST /api/v1/admin/faiss/build` is called.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from app.services.context import context_registry
from app.api.v1.router import router
import structlog

log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared Redis pool — injected into routes via app.state.redis
    app.state.redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    log.info("startup.redis.ready")

    # Startup: load persisted FAISS index from disk (skips rebuild on every restart)
    if context_registry.faiss:
        loaded = await context_registry.faiss.load_persisted()
        if loaded:
            log.info("startup.faiss.loaded_from_disk")
        else:
            log.warning("startup.faiss.no_index_found", hint="Call POST /api/v1/admin/faiss/build to build")

    yield

    # Shutdown: close Redis pool cleanly
    await app.state.redis.close()
    log.info("shutdown.redis.closed")

app = FastAPI(title="CV Optimizer", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")
```

```bash
# File upload
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "cv_file=@my_cv.pdf" -F "jd_file=@jd.docx"

# Plain text
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "cv_text=John Doe, Python engineer..." \
  -F "jd_text=We are looking for a senior backend..."

# Mixed (file CV + text JD)
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "cv_file=@my_cv.pdf" \
  -F "jd_text=We are looking for a senior backend..."

# Poll
curl http://localhost:8000/api/v1/jobs/abc-123

# Trigger FAISS rebuild (after enough completed jobs exist)
curl -X POST http://localhost:8000/api/v1/admin/faiss/build
```

---

## LangGraph Workflow

### State — `agents/state.py`

```python
from typing import TypedDict
from app.models.schemas import CVData, JDData, MatchResult, GenerateResult, InputPayload
from app.services.context.base import ContextChunk, KnowledgeDoc

class WorkflowState(TypedDict):
    job_id: str
    cv_input: InputPayload
    jd_input: InputPayload
    cv_data: CVData | None
    jd_data: JDData | None
    knowledge_docs: list[KnowledgeDoc]    # .md files → passed as Anthropic document blocks
    context_chunks: list[ContextChunk]    # dynamic similarity results (FAISS, DB)
    match_result: MatchResult | None
    new_cv_markdown: str | None
    generate_result: GenerateResult | None
    error: str | None
    current_step: str
```

### Graph — `agents/workflow.py`

```
parse → validate → context → match → rewrite → format → END
              ↓ (error)
             END
```

```python
from langgraph.graph import StateGraph, END
from app.agents.state import WorkflowState
from app.agents.nodes import parse_node, validate_node, context_node, match_node, rewrite_node, format_node

def build_workflow():
    g = StateGraph(WorkflowState)
    for name, fn in [("parse", parse_node.run), ("validate", validate_node.run),
                     ("context", context_node.run), ("match", match_node.run),
                     ("rewrite", rewrite_node.run), ("format", format_node.run)]:
        g.add_node(name, fn)
    g.set_entry_point("parse")
    g.add_edge("parse", "validate")
    g.add_conditional_edges("validate",
        lambda s: "error" if s.get("error") else "context",
        {"context": "context", "error": END})
    g.add_edge("context", "match")
    g.add_edge("match",   "rewrite")
    g.add_edge("rewrite", "format")
    g.add_edge("format",  END)
    return g.compile()

workflow = build_workflow()
```

### Nodes

**`parse_node.py`** — resolves parser from `InputPayload`, extracts text, calls LLM for structured JSON.

> ⚠️ LLM prompt must say: "return valid JSON only, do NOT hallucinate missing fields".

```python
import structlog
from app.agents.state import WorkflowState
from app.services.parser import ParserService
from app.core.llm_factory import LLMFactory
from app.core.exceptions import ParseError

log = structlog.get_logger()
parser = ParserService()

async def run(state: WorkflowState) -> WorkflowState:
    log.info("parse_node.start", job_id=state["job_id"])
    try:
        cv_inp, jd_inp = state["cv_input"], state["jd_input"]
        cv_text = (await parser.parse_file(cv_inp.raw, cv_inp.filename, cv_inp.content_type)
                   if cv_inp.raw else await parser.parse_text(cv_inp.text))
        jd_text = (await parser.parse_file(jd_inp.raw, jd_inp.filename, jd_inp.content_type)
                   if jd_inp.raw else await parser.parse_text(jd_inp.text))
        llm = LLMFactory.create()
        cv_data = await _extract_structured(llm, cv_text, "CV")   # → CVData JSON
        jd_data = await _extract_structured(llm, jd_text, "JD")   # → JDData JSON
        return {**state, "cv_data": cv_data, "jd_data": jd_data, "current_step": "parse"}
    except Exception as e:
        log.error("parse_node.error", job_id=state["job_id"], error=str(e))
        raise ParseError(str(e)) from e
```

**`validate_node.py`** — guards against bad LLM JSON corrupting downstream nodes.

```python
import structlog
from app.agents.state import WorkflowState
from app.models.schemas import CVData, JDData

log = structlog.get_logger()

async def run(state: WorkflowState) -> WorkflowState:
    errors = []
    for cls, key in [(CVData, "cv_data"), (JDData, "jd_data")]:
        try: cls.model_validate(state[key])
        except Exception as e: errors.append(f"{key}: {e}")
    if errors:
        log.warning("validate_node.failed", job_id=state["job_id"], errors=errors)
        return {**state, "error": "; ".join(errors), "current_step": "validate"}
    return {**state, "current_step": "validate"}
```

**`context_node.py`** — loads `.md` docs AND dynamic chunks; downstream nodes receive both separately.

> ⚠️ `knowledge_docs` always loaded from `app/knowledge/` regardless of `context_providers` setting.
> ⚠️ `context_chunks` come from dynamic providers (FAISS, DB) gated by `context_providers`.
> ⚠️ Provider failures logged and skipped — never crash the workflow for a context miss.

```python
import structlog
from app.agents.state import WorkflowState
from app.services.context import context_registry

log = structlog.get_logger()

async def run(state: WorkflowState) -> WorkflowState:
    cv, jd = state["cv_data"], state["jd_data"]
    query = f"{jd.title} {' '.join(jd.required_skills)} {' '.join(cv.skills)}"

    # .md knowledge docs — always included, passed as Anthropic document blocks
    docs = await context_registry.gather_docs(query)

    # Dynamic context — FAISS similarity, past DB results, etc.
    chunks = await context_registry.gather_chunks(query)

    log.info("context_node.done", job_id=state["job_id"],
             docs=len(docs), chunks=len(chunks),
             doc_files=[d.filename for d in docs],
             chunk_sources=list({c.source for c in chunks}))

    return {**state, "knowledge_docs": docs, "context_chunks": chunks, "current_step": "context"}
```

**`rewrite_node.py`** — builds Anthropic multi-block message: knowledge docs as document blocks first, then the rewrite prompt. Falls back to inline text for non-Anthropic providers.

> ⚠️ Never handle output formatting here — that belongs in `format_node`.
> ⚠️ Document blocks must come before the `text` block in the Anthropic message.
> ⚠️ For OpenAI/Groq, docs are prepended as text sections — same content, different transport.

```python
import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from app.agents.state import WorkflowState
from app.core.llm_factory import LLMFactory
from app.core.config import settings

log = structlog.get_logger()

PROMPT_TEMPLATE = """
Rewrite the CV to better match the JD. Rules:
- DO NOT fabricate experience, skills, or achievements not in the original CV
- DO reorder sections to highlight JD-relevant experience first
- DO use stronger action verbs and incorporate ATS keywords naturally
- DO add measurable outcomes only if inferable from existing content
- Refer to the reference documents provided for skill standards, ATS keywords, and style rules
- Output Markdown only — no commentary

Original CV:
{cv_json}

Job Description:
{jd_json}

Match analysis:
{match_json}

Missing skills (DO NOT present as candidate experience):
{missing_skills}
{dynamic_context}
"""


def _build_message(state: WorkflowState, prompt_text: str) -> HumanMessage:
    """
    Build message with knowledge docs as Anthropic document blocks.
    For non-Anthropic providers, docs are prepended inline as text sections.
    """
    docs = state.get("knowledge_docs", [])

    if settings.llm_provider == "claude" and docs:
        # Anthropic: structured document blocks — Claude reads markdown natively
        content = [doc.to_anthropic_block() for doc in docs]
        content.append({"type": "text", "text": prompt_text})
        return HumanMessage(content=content)
    else:
        # OpenAI / Groq: prepend docs as inline text sections
        doc_sections = "\n\n".join(doc.to_text_section() for doc in docs)
        full_text = f"{doc_sections}\n\n---\n\n{prompt_text}" if doc_sections else prompt_text
        return HumanMessage(content=full_text)


async def run(state: WorkflowState) -> WorkflowState:
    llm = LLMFactory.create()

    dynamic_context = ""
    if state.get("context_chunks"):
        lines = "\n---\n".join(f"[{c.source}] {c.content}" for c in state["context_chunks"])
        dynamic_context = f"\nSimilar past CVs / additional context:\n{lines}"

    prompt_text = PROMPT_TEMPLATE.format(
        cv_json=state["cv_data"].model_dump_json(indent=2),
        jd_json=state["jd_data"].model_dump_json(indent=2),
        match_json=state["match_result"].model_dump_json(indent=2),
        missing_skills=state["match_result"].missing_skills,
        dynamic_context=dynamic_context,
    )

    message = _build_message(state, prompt_text)
    log.info("rewrite_node.start", job_id=state["job_id"],
             docs_attached=len(state.get("knowledge_docs", [])),
             provider=settings.llm_provider)

    response = await llm.ainvoke([message])
    return {**state, "new_cv_markdown": response.content, "current_step": "rewrite"}
```

**`format_node.py`** — assembles final result, records which context sources contributed.

```python
from app.models.schemas import GenerateResult
from app.core.config import settings

async def run(state: WorkflowState) -> WorkflowState:
    doc_sources  = [f"knowledge:{d.filename}" for d in state.get("knowledge_docs", [])]
    chunk_sources = list({c.source for c in state.get("context_chunks", [])})
    result = GenerateResult(
        cv_markdown=state["new_cv_markdown"],
        match_result=state["match_result"],
        processing_time_ms=0,
        llm_model_used=settings.llm_provider,
        context_sources=doc_sources + chunk_sources,
    )
    return {**state, "generate_result": result, "current_step": "format"}
```

---

## Services

### Matcher — `services/matcher.py`

> Uses synonym/equivalence rules from `knowledge/skills/*.md` docs to expand skill matching before scoring.

```python
import json, structlog, re
from langchain_core.language_models import BaseChatModel
from app.models.schemas import CVData, JDData, MatchResult
from app.services.context.base import ContextChunk, KnowledgeDoc
from app.core.llm_factory import LLMFactory

log = structlog.get_logger()

class MatcherService:
    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm or LLMFactory.create()

    async def match(
        self,
        cv: CVData,
        jd: JDData,
        knowledge_docs: list[KnowledgeDoc] | None = None,
        context_chunks: list[ContextChunk] | None = None,
    ) -> MatchResult:
        cv_s = {s.lower() for s in cv.skills}
        jd_r = {s.lower() for s in jd.required_skills}
        jd_p = {s.lower() for s in jd.preferred_skills}

        # Expand using synonym rules parsed from knowledge .md files
        synonyms = self._parse_synonyms(knowledge_docs or [])
        cv_s_exp = cv_s | {synonyms.get(s, s) for s in cv_s}
        jd_r_exp = jd_r | {synonyms.get(s, s) for s in jd_r}

        matching = list(cv_s_exp & jd_r_exp)
        missing  = list(jd_r - cv_s_exp)
        strong   = list(cv_s_exp & (jd_r_exp | jd_p))
        score    = round(len(matching) / max(len(jd_r), 1) * 100, 1)

        return MatchResult(
            score=score, matching_skills=matching, missing_skills=missing,
            strong_skills=strong, suggestions=await self._suggestions(cv, jd, missing),
            ats_keywords=list(jd_r | jd_p)[:20],
        )

    def _parse_synonyms(self, docs: list[KnowledgeDoc]) -> dict[str, str]:
        """
        Parse "Synonyms & equivalences" sections from skill .md files.
        Pattern: `- Alias = Canonical` or `- Alias = CanonicalA = CanonicalB`
        """
        synonyms: dict[str, str] = {}
        for doc in docs:
            in_synonyms = False
            for line in doc.content.splitlines():
                if "synonym" in line.lower() or "equivalen" in line.lower():
                    in_synonyms = True; continue
                if in_synonyms:
                    if line.startswith("#"): in_synonyms = False; continue
                    match = re.match(r"-\s*(.+)", line.strip())
                    if match:
                        parts = [p.strip().lower() for p in match.group(1).split("=")]
                        canonical = parts[-1]
                        for alias in parts[:-1]:
                            synonyms[alias] = canonical
        return synonyms

    async def _suggestions(self, cv, jd, missing) -> list[str]:
        prompt = (f"CV skills: {cv.skills}\nJD requires: {jd.required_skills}\nMissing: {missing}\n"
                  "Return a JSON array of 3-5 actionable suggestion strings. Output ONLY the JSON array, no preamble, no markdown.")
        r = await self.llm.ainvoke(prompt)
        try:
            # Strip markdown fences if LLM wraps output (e.g. ```json ... ```)
            raw = r.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(raw)
        except (json.JSONDecodeError, AttributeError):
            log.warning("matcher.suggestions.parse_error", raw=r.content[:200])
            return []   # graceful fallback — match result still valid without suggestions
```

---

## Worker — `workers/cv_worker.py`

> ⚠️ `POST /jobs` must not block — it enqueues and returns 202. All LLM work happens here.
> ⚠️ Log every step keyed by `job_id`. Include `context_sources` in `worker.done`.
> ⚠️ `enqueue_cv_job` receives a shared `ArqRedis` pool from FastAPI lifespan — never creates a new pool per request.

```python
import time, structlog
from arq.connections import ArqRedis
from app.agents.workflow import workflow
from app.agents.state import WorkflowState
from app.models.schemas import InputPayload
from app.core.config import settings

log = structlog.get_logger()

async def process_cv_job(ctx: dict, job_id: str, cv: InputPayload, jd: InputPayload):
    repo = ctx["repo"]
    await repo.update_status(job_id, "processing")
    t0 = time.monotonic()
    try:
        state: WorkflowState = {
            "job_id": job_id, "cv_input": cv, "jd_input": jd,
            "cv_data": None, "jd_data": None,
            "knowledge_docs": [], "context_chunks": [],
            "match_result": None, "new_cv_markdown": None,
            "generate_result": None, "error": None, "current_step": "start",
        }
        final = await workflow.ainvoke(state)
        if final.get("error"):
            await repo.update_status(job_id, "failed", error=final["error"]); return
        result = final["generate_result"]
        result.processing_time_ms = round((time.monotonic() - t0) * 1000)
        await repo.update_status(job_id, "done", result=result.model_dump())
        log.info("worker.done", job_id=job_id, elapsed_ms=result.processing_time_ms,
                 knowledge_docs=len(final.get("knowledge_docs", [])),
                 context_sources=result.context_sources)
    except Exception as e:
        log.error("worker.exception", job_id=job_id, error=str(e))
        await repo.update_status(job_id, "failed", error=str(e)); raise

# Shared pool injected from FastAPI lifespan — never create a new pool per request.
async def enqueue_cv_job(redis: ArqRedis, job_id: str, cv: InputPayload, jd: InputPayload):
    await redis.enqueue_job("process_cv_job", job_id, cv, jd)

class WorkerSettings:
    functions = [process_cv_job]
    redis_settings = settings.redis_url
    max_jobs = settings.max_concurrent_jobs
    job_timeout = settings.job_timeout_seconds
```

---

## Logging

> ⚠️ Every log call must include `job_id=`. Context sources must appear in `worker.done`.

```python
# core/logging.py
import structlog, logging
from app.core.config import settings

def configure_logging():
    structlog.configure(
        processors=[structlog.stdlib.add_log_level, structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.format_exc_info, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(), cache_logger_on_first_use=True,
    )
```

```json
{"event":"parse_node.start",   "job_id":"abc-123"}
{"event":"validate_node.done", "job_id":"abc-123"}
{"event":"context_node.done",  "job_id":"abc-123","total_chunks":12,"sources":["faiss","static:skill_taxonomy.yaml"]}
{"event":"match_node.done",    "job_id":"abc-123","score":78.5}
{"event":"rewrite_node.start", "job_id":"abc-123"}
{"event":"worker.done",        "job_id":"abc-123","elapsed_ms":14200,"context_sources":["faiss","static:skill_taxonomy.yaml"]}
```

---

## Testing

> ⚠️ `InMemoryJobRepository` in all tests — no real DB or Redis.
> ⚠️ Mock `BaseChatModel` injected — no real LLM calls in unit tests.
> ⚠️ Pass `context=[]` to services in unit tests — no FAISS index or DB needed.

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock
from app.repositories.job_repository import InMemoryJobRepository

@pytest.fixture
def repo(): return InMemoryJobRepository()

@pytest.fixture
def mock_llm():
    m = AsyncMock()
    m.ainvoke.return_value.content = '["Highlight cloud experience"]'
    return m
```

```python
# tests/unit/test_matcher.py
import pytest
from app.services.matcher import MatcherService
from app.models.schemas import CVData, JDData, Experience, Education

@pytest.fixture
def cv():
    return CVData(name="Jane", skills=["Python","FastAPI","Docker"],
        experience=[Experience(company="Acme",title="Eng",start_date="2022-01",bullets=["Built APIs"])],
        education=[Education(institution="Uni",degree="BSc",field="CS")])

@pytest.fixture
def jd():
    return JDData(title="Senior Eng", required_skills=["Python","FastAPI","Kubernetes"],
        preferred_skills=["Docker"], responsibilities=["Build APIs"])

@pytest.mark.asyncio
async def test_score_range(mock_llm, cv, jd):
    result = await MatcherService(llm=mock_llm).match(cv, jd, context=[])
    assert 0 <= result.score <= 100
    assert "python" in result.matching_skills
    assert "kubernetes" in result.missing_skills

@pytest.mark.asyncio
async def test_taxonomy_expands_skills(mock_llm, cv, jd):
    from app.services.context.base import ContextChunk
    chunk = ContextChunk(content="FastAPI: web_framework", source="static:skill_taxonomy.yaml")
    result = await MatcherService(llm=mock_llm).match(cv, jd, context=[chunk])
    assert result.score >= 0
```

```python
# tests/unit/test_parser.py
import pytest
from app.services.parser import ParserService

@pytest.mark.asyncio
async def test_parse_plain_text():
    result = await ParserService().parse_text("John Doe, Python engineer")
    assert "John Doe" in result

@pytest.mark.asyncio
async def test_unsupported_format_raises():
    from app.core.exceptions import ParseError
    with pytest.raises(ParseError):
        await ParserService().parse_file(b"data", "resume.xyz")
```

---

## Docker

```yaml
# docker-compose.yml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis:    {condition: service_healthy}

  worker:
    build: .
    command: python -m arq app.workers.cv_worker.WorkerSettings
    env_file: .env
    depends_on: [api]

  postgres:
    image: postgres:16-alpine
    environment: {POSTGRES_USER: user, POSTGRES_PASSWORD: pass, POSTGRES_DB: cvoptimizer}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL","pg_isready -U user"]
      interval: 5s; timeout: 5s; retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD","redis-cli","ping"]
      interval: 5s; timeout: 5s; retries: 5

volumes:
  pgdata:
```

```bash
docker compose up --build

# Without Docker
uvicorn app.main:app --reload &
arq app.workers.cv_worker.WorkerSettings
```

---

## Extension Guide

### Add a new input format (e.g. `.rtf`)

1. Create `services/parser/rtf_parser.py` with `media_types`, `extensions`, `extract_text`
2. Append `RTFParser()` to `_registry` in `services/parser/__init__.py`
3. Add `"rtf"` to `allowed_input_types` in `.env`

### Add a new context provider (e.g. internal HR system)
1. Create `services/context/hr_provider.py` implementing `ContextProvider`
2. Add `"hr": lambda: HRContextProvider(...)` to `_PROVIDER_FACTORIES` in `services/context/__init__.py`
3. Add `"hr"` to `context_providers` in `.env`

### Add internal knowledge data
1. Drop any `.md` file into `app/knowledge/`
2. `MarkdownDocProvider` picks it up on next startup — no code change
3. Optionally add a `context_hint` entry in `_HINTS` inside `markdown_provider.py`

### Seed and build the FAISS index
1. Process at least a handful of CVs through the system (status=`done`)
2. Call `POST /api/v1/admin/faiss/build` — builds from all completed jobs and persists index to `data/`
3. On all future restarts, `main.py` lifespan calls `faiss.load_persisted()` automatically — no rebuild needed

### Disable a provider temporarily
Remove its name from `CONTEXT_PROVIDERS` in `.env` — no code change, no restart of other services needed.

---

## Bonus Features

| Priority | Feature | Where |
|---|---|---|
| High | ATS keyword optimization | `MatchResult.ats_keywords` → rewriter prompt (done) |
| High | Score improvement tips | `MatchResult.suggestions` → expose via API (done) |
| Medium | Past CV reuse | `DBContextProvider.gather()` — query done jobs with score ≥ 75 |
| Medium | PDF export | `weasyprint` in `format_node` |
| Medium | Domain knowledge enrichment | Add `.yaml` to `app/knowledge/` |
| Low | Multi-language | Detect lang in `parse_node`, pass locale to rewriter prompt |
| Low | Session memory | Store `CVData` in Redis keyed by user session |

---

## Checklist

- [ ] All routes prefixed `/api/v1/`
- [ ] `POST /jobs` returns 202, never blocks on LLM
- [ ] API accepts file upload OR plain text for CV and JD (including mixed)
- [ ] File type validated against `settings.allowed_input_types`
- [ ] File size validated before enqueuing
- [ ] All services accept `BaseChatModel`, never concrete LLM class
- [ ] All services accept `AbstractJobRepository`, never SQLAlchemy directly
- [ ] `core/config.py` is only place reading `.env`
- [ ] `.env` in `.gitignore`, `.env.example` committed
- [ ] `validate_node` runs before `context_node` and `match_node`
- [ ] `context_node` skips unavailable providers without crashing
- [ ] `context_providers` in `.env` controls active providers — no code change to add/remove
- [ ] New input format: one class + one registry line + `.env` update only
- [ ] New context provider: one class + one `_PROVIDER_FACTORIES` entry + `.env` update only
- [ ] New knowledge data: drop `.md` into `app/knowledge/` only
- [ ] Rewriter prompt explicitly forbids fabricating missing skills
- [ ] Every log line includes `job_id=`
- [ ] `worker.done` log includes `context_sources=`
- [ ] `InMemoryJobRepository` in all tests
- [ ] Mock LLM + empty context injected in all unit tests
- [ ] **[Fix #1]** `ContextRegistry` uses `_PROVIDER_FACTORIES` — providers instantiated lazily, not at module import
- [ ] **[Fix #2]** `FAISSContextProvider.build()` persists index to `data/faiss.index` + `data/faiss_docs.pkl`
- [ ] **[Fix #2]** `main.py` lifespan calls `faiss.load_persisted()` on startup
- [ ] **[Fix #2]** `POST /api/v1/admin/faiss/build` triggers index rebuild in background
- [ ] **[Fix #3]** `MatcherService._suggestions()` wraps `json.loads` in try/except, strips markdown fences, returns `[]` on failure
- [ ] **[Fix #4]** `ArqRedis` pool created once in `main.py` lifespan, stored in `app.state.redis`
- [ ] **[Fix #4]** `enqueue_cv_job(redis, ...)` receives pool via `Depends(get_redis)` — no per-request `create_pool`