from app.repositories.job_repository import AbstractJobRepository, InMemoryJobRepository


# Default to in-memory repo. Override via dependency in production.
_repo: AbstractJobRepository | None = None


def get_job_repository() -> AbstractJobRepository:
    global _repo
    if _repo is None:
        _repo = InMemoryJobRepository()
    return _repo


def set_job_repository(repo: AbstractJobRepository) -> None:
    global _repo
    _repo = repo
