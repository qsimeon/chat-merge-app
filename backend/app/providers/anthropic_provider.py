import logging
from typing import AsyncGenerator, Optional, List
from anthropic import AsyncAnthropic
from app.providers.base import BaseProvider, StreamChunk

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic provider implementation"""

    AVAILABLE_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-20250414",
        "claude-opus-4-20250514",
    ]

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    def _format_message_with_attachments(self, msg: dict) -> dict:
        if "attachments" not in msg or not msg["attachments"]:
            return msg

        content = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})

        for att in msg["attachments"]:
            if att["file_type"].startswith("image/"):
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": att["file_type"], "data": att["data"]}
                })
            elif att["file_type"].startswith("text/"):
                import base64
                try:
                    file_text = base64.b64decode(att['data']).decode('utf-8')
                    content.append({"type": "text", "text": f"[File: {att['file_name']}]\n{file_text}"})
                except Exception:
                    content.append({"type": "text", "text": f"[Attached file: {att['file_name']} ({att['file_type']})]"})

        return {"role": msg["role"], "content": content}

    async def stream_completion(
        self,
        messages: List[dict],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        try:
            filtered_messages = [
                self._format_message_with_attachments(m)
                for m in messages if m.get("role") != "system"
            ]

            kwargs = {
                "model": model,
                "messages": filtered_messages,
                "max_tokens": max_tokens or 8192,
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if (hasattr(event, 'type') and event.type == 'content_block_delta'
                            and hasattr(event, 'delta')
                            and hasattr(event.delta, 'type')
                            and event.delta.type == 'text_delta'
                            and hasattr(event.delta, 'text')):
                        yield StreamChunk(type="content", data=event.delta.text)

            yield StreamChunk(type="done", data="")

        except Exception as e:
            logger.error(f"Anthropic streaming error: {str(e)}")
            yield StreamChunk(type="error", data=f"Anthropic error: {str(e)}")

    def get_available_models(self) -> List[str]:
        return self.AVAILABLE_MODELS

    @staticmethod
    def get_available_models_static() -> List[str]:
        return AnthropicProvider.AVAILABLE_MODELS
