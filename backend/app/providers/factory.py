import logging
from typing import Dict, List
from app.providers.base import BaseProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def create_provider(provider_name: str, api_key: str) -> BaseProvider:
    """
    Create a provider instance

    Args:
        provider_name: Name of provider (openai, anthropic, gemini)
        api_key: API key for the provider

    Returns:
        BaseProvider instance

    Raises:
        ValueError: If provider is unknown
    """
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}")
    return PROVIDERS[provider_name](api_key)


def get_all_models() -> Dict[str, List[str]]:
    """
    Get all available models per provider

    Returns:
        Dict mapping provider names to lists of model names
    """
    return {
        name: cls.get_available_models_static()
        for name, cls in PROVIDERS.items()
    }
