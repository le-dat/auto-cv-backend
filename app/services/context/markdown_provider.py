import pathlib
from app.services.context.base import KnowledgeDoc


_HINTS: dict[str, str] = {
    "backend": "Use this to evaluate and standardize backend skill descriptions.",
    "frontend": "Use this to evaluate and standardize frontend skill descriptions.",
    "devops": "Use this to evaluate and standardize DevOps skill descriptions.",
    "data_science": "Use this to evaluate and standardize data science skill descriptions.",
    "ats_keywords": "Use the ATS keywords listed here to optimize the CV for applicant tracking systems.",
    "cv_style": "Follow these style rules strictly when rewriting the CV.",
}
_DEFAULT_HINT = "Use this reference document to improve the accuracy of your response."


class MarkdownDocProvider:
    name = "markdown"

    def __init__(self, knowledge_dir: str):
        self._dir = pathlib.Path(knowledge_dir)
        self._docs: list[KnowledgeDoc] = []
        self._loaded = False

    async def is_ready(self) -> bool:
        if not self._loaded:
            await self._load()
        return len(self._docs) > 0

    async def _load(self) -> None:
        self._docs = []
        for f in sorted(self._dir.rglob("*.md")):
            content = f.read_text(encoding="utf-8").strip()
            if not content:
                continue
            first_line = content.splitlines()[0]
            title = (
                first_line.lstrip("# ").strip()
                if first_line.startswith("#")
                else f.stem.replace("_", " ").title()
            )
            hint_key = next((k for k in _HINTS if k in f.stem.lower()), None)
            self._docs.append(
                KnowledgeDoc(
                    title=title,
                    content=content,
                    filename=str(f.relative_to(self._dir)),
                    context_hint=_HINTS.get(hint_key or "", _DEFAULT_HINT),
                    always_include=True,
                )
            )
        self._loaded = True

    async def gather(self, query: str, top_k: int) -> list[KnowledgeDoc]:
        # always_include=True → return all docs (Claude handles relevance internally)
        always = [d for d in self._docs if d.always_include]
        ranked = [d for d in self._docs if not d.always_include]
        if ranked:
            q = set(query.lower().split())
            ranked.sort(
                key=lambda d: len(q & set(d.content.lower().split())),
                reverse=True,
            )
        return (always + ranked)[:top_k]
