import logging
from typing import AsyncGenerator, Optional, List
from openai import AsyncOpenAI
from app.providers.base import BaseProvider, StreamChunk

logger = logging.getLogger(__name__)

# Models that support reasoning tokens (o-series)
REASONING_MODELS = {"o1", "o1-mini", "o1-pro", "o3", "o3-mini", "o4-mini"}


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation with reasoning token capture"""

    AVAILABLE_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o4-mini",
        "o3",
        "o3-mini",
    ]

    def __init__(self, api_key: str):
        """Initialize OpenAI provider"""
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if this model supports reasoning tokens"""
        model_lower = model.lower()
        return any(model_lower.startswith(rm) for rm in REASONING_MODELS)

    async def stream_completion(
        self,
        messages: List[dict],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream completion from OpenAI with reasoning token capture"""
        try:
            is_reasoning = self._is_reasoning_model(model)

            # Build message list
            request_messages = messages.copy()
            if system_prompt:
                if is_reasoning:
                    # o-series models use "developer" role instead of "system"
                    request_messages.insert(0, {
                        "role": "developer",
                        "content": system_prompt
                    })
                else:
                    request_messages.insert(0, {
                        "role": "system",
                        "content": system_prompt
                    })

            # Build API kwargs
            kwargs = {
                "model": model,
                "messages": request_messages,
                "stream": True,
            }

            if is_reasoning:
                # o-series models: no temperature param, use reasoning effort
                # Include reasoning summary in streaming output
                kwargs["stream_options"] = {"include_usage": True}
                if max_tokens:
                    kwargs["max_completion_tokens"] = max_tokens
                else:
                    kwargs["max_completion_tokens"] = 16384
                # Request reasoning summaries to be included
                kwargs["reasoning"] = {"effort": "high", "summary": "auto"}
            else:
                # Standard models
                kwargs["temperature"] = temperature
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens

            # Stream from OpenAI
            stream = await self.client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = choice.delta

                    if delta:
                        # Capture reasoning content from o-series models
                        # The reasoning field appears in the delta for reasoning models
                        if hasattr(delta, 'reasoning') and delta.reasoning:
                            # reasoning can be a dict or object with 'summary' field
                            reasoning_text = None
                            if isinstance(delta.reasoning, str):
                                reasoning_text = delta.reasoning
                            elif hasattr(delta.reasoning, 'summary') and delta.reasoning.summary:
                                # Reasoning summaries come as a list of summary objects
                                for summary in delta.reasoning.summary:
                                    if hasattr(summary, 'text') and summary.text:
                                        yield StreamChunk(
                                            type="reasoning",
                                            data=summary.text
                                        )
                            elif isinstance(delta.reasoning, dict):
                                reasoning_text = delta.reasoning.get('summary', '') or delta.reasoning.get('content', '')

                            if reasoning_text:
                                yield StreamChunk(
                                    type="reasoning",
                                    data=reasoning_text
                                )

                        # Standard content
                        if delta.content:
                            yield StreamChunk(
                                type="content",
                                data=delta.content
                            )

            # Signal completion
            yield StreamChunk(type="done", data="")

        except Exception as e:
            logger.error(f"OpenAI streaming error: {str(e)}")
            yield StreamChunk(type="error", data=f"OpenAI error: {str(e)}")

    @staticmethod
    def get_available_models_static() -> List[str]:
        """Get available OpenAI models"""
        return OpenAIProvider.AVAILABLE_MODELS
