from typing import Protocol, runtime_checkable, Any
from dataclasses import dataclass, field


@dataclass
class ContextChunk:
    """Dynamic context — retrieved at runtime (FAISS, DB, HTTP)."""
    content: str
    source: str
    score: float = 1.0


@dataclass
class KnowledgeDoc:
    """
    Static internal .md file — passed directly to Claude as a document block.
    Claude reads the full file with its markdown structure intact.
    For non-Anthropic providers, content is prepended to the prompt as a text section.
    """
    title: str
    content: str
    filename: str
    context_hint: str
    always_include: bool = True

    def to_anthropic_block(self) -> dict[str, Any]:
        """Serialize to Anthropic document content block."""
        return {
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": self.content,
            },
            "title": self.title,
            "context": self.context_hint,
            "citations": {"enabled": False},
        }

    def to_text_section(self) -> str:
        """Fallback for non-Anthropic providers — inline as a prompt section."""
        return f"## Reference: {self.title}\n\n{self.content}\n"


@runtime_checkable
class ContextProvider(Protocol):
    name: str

    async def is_ready(self) -> bool:
        ...

    async def gather(self, query: str, top_k: int) -> list[ContextChunk]:
        ...
