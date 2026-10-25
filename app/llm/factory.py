from app.core.config import Settings
from app.llm.anthropic_client import AnthropicClient
from app.llm.azure_openai_client import AzureOpenAIClient
from app.llm.base import LLMClient
from app.llm.fake import FakeLLM
from app.llm.openai_compat import OpenAICompatibleClient


def build_llm_client(settings: Settings) -> LLMClient:
    provider = settings.LLM_PROVIDER
    if provider == "fake":
        if settings.is_production:
            raise RuntimeError("The fake LLM provider is not allowed in production.")
        return FakeLLM()
    if provider == "openai_compatible":
        return OpenAICompatibleClient(
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("LABDOCS_ANTHROPIC_API_KEY is required for the Anthropic provider.")
        return AnthropicClient(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.ANTHROPIC_BASE_URL,
            version=settings.ANTHROPIC_VERSION,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    if not settings.AZURE_OPENAI_ENDPOINT:
        raise RuntimeError(
            "LABDOCS_AZURE_OPENAI_ENDPOINT is required for the Azure OpenAI provider."
        )
    if not settings.AZURE_OPENAI_API_KEY:
        raise RuntimeError(
            "LABDOCS_AZURE_OPENAI_API_KEY is required for the Azure OpenAI provider."
        )
    if not settings.AZURE_OPENAI_DEPLOYMENT:
        raise RuntimeError(
            "LABDOCS_AZURE_OPENAI_DEPLOYMENT is required for the Azure OpenAI provider."
        )
    return AzureOpenAIClient(
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        max_retries=settings.LLM_MAX_RETRIES,
    )
