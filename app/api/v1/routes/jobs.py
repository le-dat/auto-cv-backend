from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request
from arq.connections import ArqRedis
from app.models.schemas import (
    JobCreateResponse,
    JobStatusResponse,
    JobRecord,
    InputPayload,
)
from app.repositories.job_repository import AbstractJobRepository
from app.core.dependencies import get_job_repository
from app.workers.cv_worker import enqueue_cv_job
from app.core.config import settings

router = APIRouter()
MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


def get_redis(request: Request) -> ArqRedis:
    return request.app.state.redis


def _make_payload(
    file: UploadFile | None, text: str | None, field: str
) -> InputPayload:
    if file and text:
        raise HTTPException(422, f"{field}: provide file OR text, not both")
    if not file and not text:
        raise HTTPException(422, f"{field}: file or text required")
    if text:
        return InputPayload(text=text, filename="input.txt", content_type="text/plain")
    if file is None:
        raise HTTPException(422, f"{field}: file or text required")
    filename = file.filename or "unknown"
    content_type = file.content_type or "application/octet-stream"
    return InputPayload(filename=filename, content_type=content_type)


@router.post("", response_model=JobCreateResponse, status_code=202)
async def create_job(
    cv_file: UploadFile | None = File(None),
    jd_file: UploadFile | None = File(None),
    cv_text: str | None = Form(None),
    jd_text: str | None = Form(None),
    repo: AbstractJobRepository = Depends(get_job_repository),
    redis: ArqRedis = Depends(get_redis),
):
    cv = _make_payload(cv_file, cv_text, "cv")
    jd = _make_payload(jd_file, jd_text, "jd")
    if cv_file:
        cv.raw = await cv_file.read()
    if jd_file:
        jd.raw = await jd_file.read()
    for p, name in [(cv, "cv"), (jd, "jd")]:
        if p.raw and len(p.raw) > MAX_BYTES:
            raise HTTPException(
                413, f"{name}_file exceeds {settings.max_file_size_mb} MB limit"
            )
        ext = p.filename.rsplit(".", 1)[-1].lower()
        if p.raw and ext not in settings.allowed_input_types:
            raise HTTPException(
                422,
                f"Unsupported format: {ext}. Allowed: {settings.allowed_input_types}",
            )
    job = JobRecord()
    await repo.save(job)
    await enqueue_cv_job(redis, job.id, cv, jd)
    return JobCreateResponse(
        job_id=job.id,
        status="pending",
        message=f"Poll GET /api/v1/jobs/{job.id}",
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    repo: AbstractJobRepository = Depends(get_job_repository),
):
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    data = job.model_dump()
    data["job_id"] = data.pop("id")
    return JobStatusResponse(**data)
