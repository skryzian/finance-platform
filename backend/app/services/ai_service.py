from app.ai.service import AIService, AIUnavailable, ToolRegistry
from app.core.config import settings
from app.services.openai_provider import OpenAIProvider


def create_ai_service() -> AIService:
    if not settings.openai_enabled:
        raise AIUnavailable("Financial Copilot is disabled")
    if settings.ai_provider != "openai":
        raise AIUnavailable("Configured AI provider is not available")
    if not settings.openai_api_key or not settings.openai_model:
        raise AIUnavailable("OpenAI credentials or model are not configured")

    provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        model_name=settings.openai_model,
        timeout_seconds=settings.ai_request_timeout_seconds,
        temperature=settings.ai_temperature,
    )
    return AIService(provider=provider, tools=ToolRegistry())
