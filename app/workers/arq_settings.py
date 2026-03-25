from app.workers.cv_worker import process_cv_job
from app.core.config import settings


class WorkerSettings:
    functions = [process_cv_job]
    redis_settings = settings.redis_url
    max_jobs = settings.max_concurrent_jobs
    job_timeout = settings.job_timeout_seconds
