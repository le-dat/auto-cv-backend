import structlog
from app.agents.state import WorkflowState
from app.models.schemas import CVData, JDData

log = structlog.get_logger()


async def run(state: WorkflowState) -> WorkflowState:
    errors = []
    for cls, key in [(CVData, "cv_data"), (JDData, "jd_data")]:
        try:
            cls.model_validate(state[key])
        except Exception as e:
            errors.append(f"{key}: {e}")
    if errors:
        log.warning("validate_node.failed", job_id=state["job_id"], errors=errors)
        return {**state, "error": "; ".join(errors), "current_step": "validate"}
    return {**state, "current_step": "validate"}
