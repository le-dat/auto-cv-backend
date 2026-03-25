from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM
    llm_provider: Literal["openai", "groq", "claude"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama3-70b-8192"
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"

    # Infrastructure
    database_url: str = ""  # Must be set in production
    redis_url: str = "redis://localhost:6379"
    allowed_origins: list[str] = []  # Set explicit origins for credentials

    # Input — extend by adding to allowed_input_types
    max_file_size_mb: int = 10
    allowed_input_types: list[str] = ["pdf", "docx", "txt", "text", "md"]

    # Context providers — resolved in order, all active providers contribute chunks
    # Enable:  add name to list.  Disable: remove name.  No code change needed.
    context_providers: list[str] = ["markdown", "faiss"]
    context_top_k: int = 5
    # Markdown knowledge docs
    knowledge_dir: str = "app/knowledge"
    knowledge_max_docs: int = 10
    db_context_enabled: bool = False
    http_context_url: str = ""

    # Limits
    max_concurrent_jobs: int = 5
    job_timeout_seconds: int = 120
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
