from app.services.context.base import ContextChunk
from app.core.config import settings


class DBContextProvider:
    name = "db"

    async def is_ready(self) -> bool:
        return settings.db_context_enabled

    async def gather(self, query: str, top_k: int) -> list[ContextChunk]:
        # SELECT cv_markdown, match_score FROM job_results
        # WHERE status='done' AND match_score >= 75 ORDER BY match_score DESC LIMIT top_k
        return []
