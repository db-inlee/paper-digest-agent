"""LLM factory for creating appropriate client instances."""

from typing import Literal

from rtc.config import get_settings
from rtc.llm.base import BaseLLMClient
from rtc.llm.claude import ClaudeLLMClient
from rtc.llm.openai import OpenAILLMClient


class LLMFactory:
    """Factory for creating LLM client instances."""

    _instance: BaseLLMClient | None = None

    @classmethod
    def create(
        cls,
        provider: Literal["claude", "openai"] | None = None,
        model: str | None = None,
    ) -> BaseLLMClient:
        """Create an LLM client instance.

        Args:
            provider: LLM provider ("claude" or "openai"). Defaults to settings.
            model: Specific model to use. Defaults to provider default.

        Returns:
            An LLM client instance.
        """
        settings = get_settings()
        provider = provider or settings.llm_provider

        if provider == "claude":
            return ClaudeLLMClient(model=model)
        elif provider == "openai":
            return OpenAILLMClient(model=model)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @classmethod
    def get_default(cls) -> BaseLLMClient:
        """Get the default LLM client (singleton).

        Returns:
            The default LLM client instance.
        """
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance."""
        cls._instance = None


def get_llm_client(
    provider: Literal["claude", "openai"] | None = None,
    model: str | None = None,
) -> BaseLLMClient:
    """Convenience function to get an LLM client.

    Args:
        provider: LLM provider. Defaults to settings.
        model: Specific model. Defaults to provider default.

    Returns:
        An LLM client instance.
    """
    if provider is None and model is None:
        return LLMFactory.get_default()
    return LLMFactory.create(provider=provider, model=model)
