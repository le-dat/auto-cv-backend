from abc import ABC, abstractmethod
from app.models.schemas import JobRecord


class AbstractJobRepository(ABC):
    @abstractmethod
    async def save(self, job: JobRecord) -> str: ...

    @abstractmethod
    async def get(self, job_id: str) -> JobRecord | None: ...

    @abstractmethod
    async def update_status(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def list_done_cv_texts(self) -> list[str]:
        """Return CV texts from all completed jobs for FAISS indexing."""
        ...


class InMemoryJobRepository(AbstractJobRepository):
    """Use in tests — no DB required."""

    def __init__(self):
        self._store: dict[str, JobRecord] = {}

    async def save(self, job: JobRecord) -> str:
        self._store[job.id] = job
        return job.id

    async def get(self, job_id: str) -> JobRecord | None:
        return self._store.get(job_id)

    async def update_status(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        if job := self._store.get(job_id):
            job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error

    async def list_done_cv_texts(self) -> list[str]:
        return []


class PostgresJobRepository(AbstractJobRepository):
    """
    Production repository using SQLAlchemy 2.0 async.

    Note: This is a placeholder. Implement before using in production.
    """

    def __init__(self, db_session):
        self.db = db_session

    async def save(self, job: JobRecord) -> str:
        # TODO: implement with SQLAlchemy
        raise NotImplementedError("Use InMemoryJobRepository in tests")

    async def get(self, job_id: str) -> JobRecord | None:
        raise NotImplementedError("Use InMemoryJobRepository in tests")

    async def update_status(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        raise NotImplementedError("Use InMemoryJobRepository in tests")

    async def list_done_cv_texts(self) -> list[str]:
        raise NotImplementedError("Use InMemoryJobRepository in tests")
