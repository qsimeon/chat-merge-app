import logging
from typing import AsyncGenerator, Optional, List
from anthropic import AsyncAnthropic
from app.providers.base import BaseProvider, StreamChunk

logger = logging.getLogger(__name__)

# Models that support extended thinking
THINKING_MODELS = {
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
}

# Budget tokens for thinking (how much "thinking space" to allocate)
DEFAULT_THINKING_BUDGET = 10000


class AnthropicProvider(BaseProvider):
    """Anthropic provider implementation with extended thinking support"""

    AVAILABLE_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-20250414",
        "claude-opus-4-20250514",
    ]

    def __init__(self, api_key: str):
        """Initialize Anthropic provider"""
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    def _supports_thinking(self, model: str) -> bool:
        """Check if this model supports extended thinking"""
        return model in THINKING_MODELS

    def _format_message_with_attachments(self, msg: dict) -> dict:
        """Format a message with attachments for Anthropic's multimodal format"""
        if "attachments" not in msg or not msg["attachments"]:
            return msg

        # Build content array with text + images
        content = []

        # Add text content first
        if msg.get("content"):
            content.append({
                "type": "text",
                "text": msg["content"]
            })

        # Add attachments
        for att in msg["attachments"]:
            if att["file_type"].startswith("image/"):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att["file_type"],
                        "data": att["data"]
                    }
                })
            else:
                # For non-image files, include file content as text if it's a text file
                if att["file_type"].startswith("text/"):
                    import base64
                    try:
                        file_text = base64.b64decode(att['data']).decode('utf-8')
                        content.append({
                            "type": "text",
                            "text": f"[File: {att['file_name']}]\n{file_text}"
                        })
                    except:
                        content.append({
                            "type": "text",
                            "text": f"[Attached file: {att['file_name']} ({att['file_type']})]"
                        })

        return {
            "role": msg["role"],
            "content": content
        }

    async def stream_completion(
        self,
        messages: List[dict],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream completion from Anthropic with extended thinking"""
        try:
            # Filter out system messages (Anthropic uses separate system param)
            # and format messages with attachments
            filtered_messages = [
                self._format_message_with_attachments(m)
                for m in messages if m.get("role") != "system"
            ]

            supports_thinking = self._supports_thinking(model)

            # Prepare kwargs
            kwargs = {
                "model": model,
                "messages": filtered_messages,
                "max_tokens": max_tokens or 16384,
            }

            # Add system prompt if provided
            if system_prompt:
                kwargs["system"] = system_prompt

            if supports_thinking:
                # Enable extended thinking — requires temperature=1 and
                # budget_tokens < max_tokens
                kwargs["temperature"] = 1
                thinking_budget = min(
                    DEFAULT_THINKING_BUDGET,
                    (max_tokens or 16384) - 1000  # leave room for output
                )
                thinking_budget = max(thinking_budget, 1024)  # minimum budget
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": thinking_budget,
                }
            else:
                # Non-thinking models use normal temperature
                kwargs["temperature"] = temperature

            # Stream from Anthropic
            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_delta':
                            if hasattr(event, 'delta'):
                                delta = event.delta
                                if hasattr(delta, 'type'):
                                    if delta.type == 'thinking_delta' and hasattr(delta, 'thinking'):
                                        yield StreamChunk(
                                            type="reasoning",
                                            data=delta.thinking
                                        )
                                    elif delta.type == 'text_delta' and hasattr(delta, 'text'):
                                        yield StreamChunk(
                                            type="content",
                                            data=delta.text
                                        )

            # Signal completion
            yield StreamChunk(type="done", data="")

        except Exception as e:
            logger.error(f"Anthropic streaming error: {str(e)}")
            yield StreamChunk(type="error", data=f"Anthropic error: {str(e)}")

    def get_available_models(self) -> List[str]:
        """Get available Anthropic models"""
        return self.AVAILABLE_MODELS

    @staticmethod
    def get_available_models_static() -> List[str]:
        """Get available Anthropic models"""
        return AnthropicProvider.AVAILABLE_MODELS
