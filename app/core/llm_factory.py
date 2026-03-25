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
                    api_key=settings.openai_api_key,
                    temperature=0.3,
                )
            case "groq":
                return ChatGroq(
                    model=settings.groq_model,
                    api_key=settings.groq_api_key,
                    temperature=0.3,
                )
            case "claude":
                return ChatAnthropic(
                    model=settings.claude_model,
                    api_key=settings.anthropic_api_key,
                    temperature=0.3,
                )
            case _:
                raise ValueError(f"Unknown LLM provider: {provider}")
