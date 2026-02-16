import logging
from typing import AsyncGenerator, Optional, List
from google import genai
from google.genai import types
from app.providers.base import BaseProvider, StreamChunk

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """Google Gemini provider implementation using the new google-genai SDK"""

    AVAILABLE_MODELS = [
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    def __init__(self, api_key: str):
        """Initialize Gemini provider"""
        super().__init__(api_key)
        self.client = genai.Client(api_key=api_key)

    def _convert_messages(self, messages: List[dict]) -> List[types.Content]:
        """
        Convert standard message format to Gemini Content format.
        Filters out system messages (handled separately via system_instruction).
        """
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                continue
            if role == "assistant":
                role = "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )
        return contents

    async def stream_completion(
        self,
        messages: List[dict],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream completion from Gemini using the new google-genai SDK"""
        try:
            contents = self._convert_messages(messages)

            # Build config with all params directly in GenerateContentConfig
            config_kwargs = {
                "temperature": temperature,
            }
            if max_tokens:
                config_kwargs["max_output_tokens"] = max_tokens
            if system_prompt:
                config_kwargs["system_instruction"] = system_prompt

            config = types.GenerateContentConfig(**config_kwargs)

            # Use async streaming via client.aio
            async for chunk in await self.client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield StreamChunk(type="content", data=chunk.text)

            # Signal completion
            yield StreamChunk(type="done", data="")

        except Exception as e:
            logger.error(f"Gemini streaming error: {str(e)}")
            yield StreamChunk(type="error", data=f"Gemini error: {str(e)}")

    def get_available_models(self) -> List[str]:
        """Get available Gemini models"""
        return self.AVAILABLE_MODELS

    @staticmethod
    def get_available_models_static() -> List[str]:
        """Get available Gemini models"""
        return GeminiProvider.AVAILABLE_MODELS
