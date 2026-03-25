import json
import re
import structlog
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

        synonyms = self._parse_synonyms(knowledge_docs or [])
        cv_s_exp = cv_s | {synonyms.get(s, s) for s in cv_s}
        jd_r_exp = jd_r | {synonyms.get(s, s) for s in jd_r}

        matching = list(cv_s_exp & jd_r_exp)
        missing = list(jd_r - cv_s_exp)
        strong = list(cv_s_exp & (jd_r_exp | jd_p))
        score = round(len(matching) / max(len(jd_r), 1) * 100, 1)

        return MatchResult(
            score=score,
            matching_skills=matching,
            missing_skills=missing,
            strong_skills=strong,
            suggestions=await self._suggestions(cv, jd, missing),
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
                    in_synonyms = True
                    continue
                if in_synonyms:
                    if line.startswith("#"):
                        in_synonyms = False
                        continue
                    match = re.match(r"-\s*(.+)", line.strip())
                    if match:
                        parts = [p.strip().lower() for p in match.group(1).split("=")]
                        canonical = parts[-1]
                        for alias in parts[:-1]:
                            synonyms[alias] = canonical
        return synonyms

    async def _suggestions(self, cv, jd, missing) -> list[str]:
        prompt = (
            f"CV skills: {cv.skills}\n"
            f"JD requires: {jd.required_skills}\n"
            f"Missing: {missing}\n"
            "Return a JSON array of 3-5 actionable suggestion strings. "
            "Output ONLY the JSON array, no preamble, no markdown."
        )
        r = await self.llm.ainvoke(prompt)
        try:
            raw = (
                r.content.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return json.loads(raw)
        except (json.JSONDecodeError, AttributeError):
            log.warning("matcher.suggestions.parse_error", raw=r.content[:200])
            return []
