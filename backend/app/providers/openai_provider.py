import logging
from typing import AsyncGenerator, Optional, List
from openai import AsyncOpenAI
from app.providers.base import BaseProvider, StreamChunk

logger = logging.getLogger(__name__)

# o-series models use different API params (max_completion_tokens, no temperature)
O_SERIES_MODELS = {"o1", "o1-mini", "o1-pro", "o3", "o3-mini", "o4-mini"}


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation"""

    AVAILABLE_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o4-mini",
        "o3",
        "o3-mini",
    ]

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)

    def _is_o_series(self, model: str) -> bool:
        return any(model.lower().startswith(m) for m in O_SERIES_MODELS)

    def _format_message_with_attachments(self, msg: dict) -> dict:
        if "attachments" not in msg or not msg["attachments"]:
            return msg

        content = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})

        for att in msg["attachments"]:
            if att["file_type"].startswith("image/"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{att['file_type']};base64,{att['data']}"}
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
            is_o_series = self._is_o_series(model)

            request_messages = [self._format_message_with_attachments(msg) for msg in messages]
            if system_prompt:
                role = "developer" if is_o_series else "system"
                request_messages.insert(0, {"role": role, "content": system_prompt})

            kwargs = {"model": model, "messages": request_messages, "stream": True}

            if is_o_series:
                # o-series: no temperature, uses max_completion_tokens
                kwargs["max_completion_tokens"] = max_tokens or 16384
            else:
                kwargs["temperature"] = temperature
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens

            stream = await self.client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(type="content", data=chunk.choices[0].delta.content)

            yield StreamChunk(type="done", data="")

        except Exception as e:
            logger.error(f"OpenAI streaming error: {str(e)}")
            yield StreamChunk(type="error", data=f"OpenAI error: {str(e)}")

    @staticmethod
    def get_available_models_static() -> List[str]:
        return OpenAIProvider.AVAILABLE_MODELS
