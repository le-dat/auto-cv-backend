from pydantic import SecretStr
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from app.core.config import settings


class LLMFactory:
    @staticmethod
    def create(provider: str | None = None) -> BaseChatModel:
        provider = provider or settings.llm_provider
        match provider:
            case "openai":
                return ChatOpenAI(
                    model=settings.openai_model,
                    api_key=SecretStr(settings.openai_api_key),
                    temperature=0.3,
                )
            case "groq":
                return ChatGroq(
                    model=settings.groq_model,
                    api_key=SecretStr(settings.groq_api_key),
                    temperature=0.3,
                    stop_sequences=None,  # type: ignore
                )
            case "claude":
                return ChatAnthropic(
                    model_name=settings.claude_model,
                    api_key=SecretStr(settings.anthropic_api_key),
                    temperature=0.3,
                    timeout=None,  # type: ignore
                    stop=None,  # type: ignore
                )
            case _:
                raise ValueError(f"Unknown LLM provider: {provider}")
