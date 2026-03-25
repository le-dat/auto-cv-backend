from __future__ import annotations

from uuid import uuid4
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, EmailStr


class InputPayload(BaseModel):
    """Unified input. Exactly one of raw or text must be set."""
    raw: bytes | None = None
    text: str | None = None
    filename: str = "input.txt"
    content_type: str | None = None

    def is_valid(self) -> bool:
        return bool(self.raw) != bool(self.text)  # XOR


class Experience(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str | None = None
    bullets: list[str]


class Education(BaseModel):
    institution: str
    degree: str
    field: str
    graduation_year: int | None = None


class CVData(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    summary: str | None = None
    skills: list[str]
    experience: list[Experience]
    education: list[Education]
    projects: list[str] = []
    certifications: list[str] = []
    languages: list[str] = []


class JDData(BaseModel):
    title: str
    company_name: str | None = None
    location: str | None = None
    job_type: Literal["full-time", "part-time", "contract", "internship"] | None = None
    required_skills: list[str]
    preferred_skills: list[str] = []
    responsibilities: list[str]
    experience_required: str | None = None
    salary_range: str | None = None


class MatchResult(BaseModel):
    score: float = Field(ge=0, le=100)
    matching_skills: list[str]
    missing_skills: list[str]
    strong_skills: list[str]
    suggestions: list[str]
    ats_keywords: list[str]


class GenerateResult(BaseModel):
    cv_markdown: str
    match_result: MatchResult
    processing_time_ms: int
    llm_model_used: str
    context_sources: list[str] = []


class JobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["pending", "processing", "done", "failed"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: GenerateResult | None = None
    error: str | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: GenerateResult | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
