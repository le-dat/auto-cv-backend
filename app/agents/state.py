from typing import TypedDict
from app.models.schemas import CVData, JDData, MatchResult, GenerateResult, InputPayload
from app.services.context.base import ContextChunk, KnowledgeDoc


class WorkflowState(TypedDict):
    job_id: str
    cv_input: InputPayload
    jd_input: InputPayload
    cv_data: CVData | None
    jd_data: JDData | None
    knowledge_docs: list[KnowledgeDoc]
    context_chunks: list[ContextChunk]
    match_result: MatchResult | None
    new_cv_markdown: str | None
    generate_result: GenerateResult | None
    error: str | None
    current_step: str
