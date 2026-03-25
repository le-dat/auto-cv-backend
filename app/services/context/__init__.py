import structlog
from app.core.config import settings
from app.services.context.base import ContextChunk, KnowledgeDoc
from app.services.context.faiss_provider import FAISSContextProvider
from app.services.context.markdown_provider import MarkdownDocProvider
from app.services.context.db_provider import DBContextProvider
from app.services.context.http_provider import HTTPContextProvider

log = structlog.get_logger()

# Provider factory map — providers are instantiated lazily inside ContextRegistry,
# NOT at module import time. This avoids failures when API keys are absent (CI, tests).
_PROVIDER_FACTORIES = {
    "faiss": lambda: FAISSContextProvider(),
    "db": lambda: DBContextProvider(),
    "http": lambda: HTTPContextProvider(settings.http_context_url),
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
            (p for p in self._active if isinstance(p, FAISSContextProvider)),
            None,
        )

    async def gather_docs(self, query: str) -> list[KnowledgeDoc]:
        """Load .md knowledge files. Always called regardless of context_providers setting."""
        if not await self._markdown.is_ready():
            log.warning("context.markdown.not_ready")
            return []
        docs = await self._markdown.gather(query, top_k=settings.knowledge_max_docs)
        log.info(
            "context.docs.loaded",
            count=len(docs),
            files=[d.filename for d in docs],
        )
        return docs

    async def gather_chunks(self, query: str) -> list[ContextChunk]:
        chunks: list[ContextChunk] = []
        for provider in self._active:
            if not await provider.is_ready():
                log.debug(
                    "context.provider.skipped", provider=provider.name
                )
                continue
            try:
                results = await provider.gather(
                    query, top_k=settings.context_top_k
                )
                chunks.extend(results)
                log.debug(
                    "context.provider.ok",
                    provider=provider.name,
                    chunks=len(results),
                )
            except Exception as e:
                log.warning(
                    "context.provider.error",
                    provider=provider.name,
                    error=str(e),
                )
        # Deduplicate by content hash, sort by relevance score
        seen, deduped = set(), []
        for c in sorted(chunks, key=lambda x: x.score, reverse=True):
            h = hash(c.content[:120])
            if h not in seen:
                seen.add(h)
                deduped.append(c)
        return deduped


context_registry = ContextRegistry()
