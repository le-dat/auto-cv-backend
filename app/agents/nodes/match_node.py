import structlog
from app.agents.state import WorkflowState
from app.services.matcher import MatcherService

log = structlog.get_logger()


async def run(state: WorkflowState) -> WorkflowState:
    log.info("match_node.start", job_id=state["job_id"])
    matcher = MatcherService()
    cv = state.get("cv_data")
    jd = state.get("jd_data")
    if not cv or not jd:
        raise ValueError("CV and JD must be parsed before matching")

    match_result = await matcher.match(
        cv=cv,
        jd=jd,
        knowledge_docs=state.get("knowledge_docs", []),
        context_chunks=state.get("context_chunks", []),
    )
    return {**state, "match_result": match_result, "current_step": "match"}
