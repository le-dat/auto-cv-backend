import structlog
from app.agents.state import WorkflowState
from app.services.matcher import MatcherService

log = structlog.get_logger()
matcher = MatcherService()


async def run(state: WorkflowState) -> WorkflowState:
    log.info("match_node.start", job_id=state["job_id"])
    match_result = await matcher.match(
        cv=state["cv_data"],
        jd=state["jd_data"],
        knowledge_docs=state.get("knowledge_docs", []),
        context_chunks=state.get("context_chunks", []),
    )
    return {**state, "match_result": match_result, "current_step": "match"}
