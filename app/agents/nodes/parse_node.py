import json
import structlog
from app.agents.state import WorkflowState
from app.services.parser import ParserService
from app.core.llm_factory import LLMFactory
from app.core.exceptions import ParseError
from pydantic import ValidationError

log = structlog.get_logger()


async def run(state: WorkflowState) -> WorkflowState:
    log.info("parse_node.start", job_id=state["job_id"])
    parser = ParserService()
    try:
        cv_inp = state["cv_input"]
        jd_inp = state["jd_input"]

        cv_text = (
            await parser.parse_file(cv_inp.raw, cv_inp.filename, cv_inp.content_type)
            if cv_inp.raw
            else await parser.parse_text(cv_inp.text)
        )
        jd_text = (
            await parser.parse_file(jd_inp.raw, jd_inp.filename, jd_inp.content_type)
            if jd_inp.raw
            else await parser.parse_text(jd_inp.text)
        )

        llm = LLMFactory.create()

        cv_data = await _extract_structured(llm, cv_text, "CV")
        jd_data = await _extract_structured(llm, jd_text, "JD")

        return {
            **state,
            "cv_data": cv_data,
            "jd_data": jd_data,
            "current_step": "parse",
        }
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        log.error("parse_node.error", job_id=state["job_id"], error=str(e))
        raise ParseError(str(e)) from e


async def _extract_structured(llm, text: str, label: str) -> dict:
    """Extract structured JSON from raw text using LLM."""
    prompt = (
        f"Extract structured information from this {label} and return valid JSON only. "
        f"Do NOT fabricate missing fields. Return valid JSON with these fields when present in the text:\n\n"
        f"{text[:4000]}\n\n"
        f"Return JSON with the appropriate fields for a {label}. Output JSON only, no commentary."
    )
    response = await llm.ainvoke(prompt)
    raw = response.content.strip()
    # Strip markdown fences
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(raw)
    return data
