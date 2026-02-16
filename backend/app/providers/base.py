from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, List
from dataclasses import dataclass


@dataclass
class StreamChunk:
    """Represents a chunk from a streaming response"""
    type: str  # "content", "reasoning", "error", "done"
    data: str


class BaseProvider(ABC):
    """Abstract base class for AI providers"""

    def __init__(self, api_key: str):
        """Initialize provider with API key"""
        self.api_key = api_key

    @abstractmethod
    async def stream_completion(
        self,
        messages: List[dict],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a completion from the provider

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Yields:
            StreamChunk objects
        """
        pass

    @staticmethod
    @abstractmethod
    def get_available_models_static() -> List[str]:
        """Get list of available models for this provider"""
        pass

    def get_available_models(self) -> List[str]:
        """Get list of available models (instance method)"""
        return self.get_available_models_static()
