import httpx
from app.services.context.base import ContextChunk
from app.core.config import settings


class HTTPContextProvider:
    name = "http"

    def __init__(self, url: str):
        self._url = url

    async def is_ready(self) -> bool:
        return bool(self._url)

    async def gather(self, query: str, top_k: int) -> list[ContextChunk]:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(self._url, json={"query": query, "top_k": top_k})
            r.raise_for_status()
            return [
                ContextChunk(
                    content=i["text"],
                    source="http",
                    score=i.get("score", 0.5),
                )
                for i in r.json().get("results", [])
            ]
