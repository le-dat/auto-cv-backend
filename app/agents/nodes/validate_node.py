import structlog
from app.agents.state import WorkflowState
from app.models.schemas import CVData, JDData

log = structlog.get_logger()


async def run(state: WorkflowState) -> WorkflowState:
    errors = []
    try:
        if state["cv_data"]:
            CVData.model_validate(state["cv_data"])
        if state["jd_data"]:
            JDData.model_validate(state["jd_data"])
    except Exception as e:
        errors.append(str(e))
    if errors:
        log.warning("validate_node.failed", job_id=state["job_id"], errors=errors)
        return {**state, "error": "; ".join(errors), "current_step": "validate"}
    return {**state, "current_step": "validate"}
