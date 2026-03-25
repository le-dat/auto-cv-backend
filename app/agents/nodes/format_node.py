from app.agents.state import WorkflowState
from app.models.schemas import GenerateResult
from app.core.config import settings


async def run(state: WorkflowState) -> WorkflowState:
    doc_sources = [f"knowledge:{d.filename}" for d in state.get("knowledge_docs", [])]
    seen: set[str] = set()
    chunk_sources: list[str] = []
    for c in state.get("context_chunks", []):
        if c.source not in seen:
            seen.add(c.source)
            chunk_sources.append(c.source)
    result = GenerateResult(
        cv_markdown=state["new_cv_markdown"],
        match_result=state["match_result"],
        processing_time_ms=0,
        llm_model_used=settings.llm_provider,
        context_sources=doc_sources + chunk_sources,
    )
    return {**state, "generate_result": result, "current_step": "format"}
