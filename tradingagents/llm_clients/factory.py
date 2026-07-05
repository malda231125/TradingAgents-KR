from typing import Optional

from .base_client import BaseLLMClient
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .google_client import GoogleClient
from .cli_client import CLIClient


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Args:
        provider: LLM provider
            (openai, anthropic, google, xai, ollama, openrouter,
            claude-cli, codex-cli)
        model: Model name/identifier
        base_url: Optional base URL for API endpoint
        **kwargs: Additional provider-specific arguments
            - http_client: Custom httpx.Client for SSL proxy or certificate customization
            - http_async_client: Custom httpx.AsyncClient for async operations
            - timeout: Request timeout in seconds
            - max_retries: Maximum retry attempts
            - api_key: API key for the provider
            - callbacks: LangChain callbacks

    Returns:
        Configured BaseLLMClient instance

    Raises:
        ValueError: If provider is not supported
    """
    provider_lower = provider.lower()

    if provider_lower in ("openai", "ollama", "openrouter"):
        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)

    if provider_lower == "xai":
        return OpenAIClient(model, base_url, provider="xai", **kwargs)

    if provider_lower == "anthropic":
        return AnthropicClient(model, base_url, **kwargs)

    if provider_lower == "google":
        return GoogleClient(model, base_url, **kwargs)

    if provider_lower == "claude-cli":
        return CLIClient(model, base_url, cli_backend="claude", **kwargs)

    if provider_lower == "codex-cli":
        return CLIClient(model, base_url, cli_backend="codex", **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
