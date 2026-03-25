import structlog
from typing import Any
from langchain_core.messages import HumanMessage
from app.agents.state import WorkflowState
from app.core.llm_factory import LLMFactory
from app.core.config import settings

log = structlog.get_logger()

PROMPT_TEMPLATE = """
Rewrite the CV to better match the JD. Rules:
- DO NOT fabricate experience, skills, or achievements not in the original CV
- DO reorder sections to highlight JD-relevant experience first
- DO use stronger action verbs and incorporate ATS keywords naturally
- DO add measurable outcomes only if inferable from existing content
- Refer to the reference documents provided for skill standards, ATS keywords, and style rules
- Output Markdown only — no commentary

Original CV:
{cv_json}

Job Description:
{jd_json}

Match analysis:
{match_json}

Missing skills (DO NOT present as candidate experience):
{missing_skills}
{dynamic_context}
"""


def _build_message(state: WorkflowState, prompt_text: str) -> HumanMessage:
    """
    Build message with knowledge docs as Anthropic document blocks.
    For non-Anthropic providers, docs are prepended inline as text sections.
    """
    docs = state.get("knowledge_docs", [])

    if settings.llm_provider == "claude" and docs:
        content: list[Any] = [doc.to_anthropic_block() for doc in docs]
        content.append({"type": "text", "text": prompt_text})
        return HumanMessage(content=content)
    else:
        doc_sections = "\n\n".join(doc.to_text_section() for doc in docs)
        full_text = (
            f"{doc_sections}\n\n---\n\n{prompt_text}" if doc_sections else prompt_text
        )
        return HumanMessage(content=full_text)


async def run(state: WorkflowState) -> WorkflowState:
    llm = LLMFactory.create()

    dynamic_context = ""
    if state.get("context_chunks"):
        lines = "\n---\n".join(
            f"[{c.source}] {c.content}" for c in state["context_chunks"]
        )
        dynamic_context = f"\nSimilar past CVs / additional context:\n{lines}"

    cv = state.get("cv_data")
    jd = state.get("jd_data")
    match_res = state.get("match_result")
    if not cv or not jd or not match_res:
        raise ValueError("CV, JD, and Match Result must be present before rewrite")

    prompt_text = PROMPT_TEMPLATE.format(
        cv_json=cv.model_dump_json(indent=2),
        jd_json=jd.model_dump_json(indent=2),
        match_json=match_res.model_dump_json(indent=2),
        missing_skills=match_res.missing_skills,
        dynamic_context=dynamic_context,
    )

    message = _build_message(state, prompt_text)
    log.info(
        "rewrite_node.start",
        job_id=state["job_id"],
        docs_attached=len(state.get("knowledge_docs", [])),
        provider=settings.llm_provider,
    )

    response = await llm.ainvoke([message])
    content = response.content
    if isinstance(content, list):
        # Handle cases where response might be content blocks
        text_content = "\n".join(
            c["text"] for c in content if isinstance(c, dict) and "text" in c
        )
    else:
        text_content = str(content)

    return {**state, "new_cv_markdown": text_content, "current_step": "rewrite"}
