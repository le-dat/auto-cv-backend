import time
import structlog
from arq.connections import ArqRedis
from app.agents.workflow import workflow
from app.agents.state import WorkflowState
from app.models.schemas import InputPayload

log = structlog.get_logger()


async def process_cv_job(
    ctx: dict,
    job_id: str,
    cv: InputPayload,
    jd: InputPayload,
):
    repo = ctx["repo"]
    await repo.update_status(job_id, "processing")
    t0 = time.monotonic()
    try:
        state: WorkflowState = {
            "job_id": job_id,
            "cv_input": cv,
            "jd_input": jd,
            "cv_data": None,
            "jd_data": None,
            "knowledge_docs": [],
            "context_chunks": [],
            "match_result": None,
            "new_cv_markdown": None,
            "generate_result": None,
            "error": None,
            "current_step": "start",
        }
        final = await workflow.ainvoke(state)
        if final.get("error"):
            await repo.update_status(job_id, "failed", error=final["error"])
            return
        result = final["generate_result"]
        result.processing_time_ms = round((time.monotonic() - t0) * 1000)
        await repo.update_status(job_id, "done", result=result.model_dump())
        log.info(
            "worker.done",
            job_id=job_id,
            elapsed_ms=result.processing_time_ms,
            knowledge_docs=len(final.get("knowledge_docs", [])),
            context_sources=result.context_sources,
        )
    except Exception as e:
        log.error("worker.exception", job_id=job_id, error=str(e))
        await repo.update_status(job_id, "failed", error=str(e))
        raise


# Shared pool injected from FastAPI lifespan — never create a new pool per request.
async def enqueue_cv_job(
    redis: ArqRedis, job_id: str, cv: InputPayload, jd: InputPayload
):
    await redis.enqueue_job("process_cv_job", job_id, cv, jd)
