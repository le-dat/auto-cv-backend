import structlog
from app.agents.state import WorkflowState
from app.services.context import context_registry

log = structlog.get_logger()


async def run(state: WorkflowState) -> WorkflowState:
    cv = state["cv_data"]
    jd = state["jd_data"]
    query = f"{jd.title} {' '.join(jd.required_skills)} {' '.join(cv.skills)}"

    # .md knowledge docs — always included, passed as Anthropic document blocks
    docs = await context_registry.gather_docs(query)

    # Dynamic context — FAISS similarity, past DB results, etc.
    chunks = await context_registry.gather_chunks(query)

    log.info(
        "context_node.done",
        job_id=state["job_id"],
        docs=len(docs),
        chunks=len(chunks),
        doc_files=[d.filename for d in docs],
        chunk_sources=list({c.source for c in chunks}),
    )

    return {
        **state,
        "knowledge_docs": docs,
        "context_chunks": chunks,
        "current_step": "context",
    }
