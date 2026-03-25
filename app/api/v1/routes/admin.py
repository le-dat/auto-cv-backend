from fastapi import APIRouter, BackgroundTasks, Depends
import structlog
from app.services.context import context_registry
from app.repositories.job_repository import AbstractJobRepository
from app.core.dependencies import get_job_repository

log = structlog.get_logger()
admin_router = APIRouter(prefix="/admin")


@admin_router.post("/faiss/build", status_code=202)
async def rebuild_faiss_index(
    background_tasks: BackgroundTasks,
    repo: AbstractJobRepository = Depends(get_job_repository),
):
    """Rebuild FAISS index from all completed jobs. Persists to disk automatically."""
    background_tasks.add_task(_do_build, repo)
    return {"message": "FAISS rebuild started in background"}


async def _do_build(repo: AbstractJobRepository):
    if context_registry.faiss is None:
        log.warning("admin.faiss.not_configured")
        return
    documents = await repo.list_done_cv_texts()
    if not documents:
        log.warning("admin.faiss.no_documents")
        return
    await context_registry.faiss.build(documents)
    log.info("admin.faiss.built", count=len(documents))
