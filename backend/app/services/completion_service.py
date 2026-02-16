import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Chat, Message, APIKey
from app.providers.factory import create_provider
from app.providers.base import StreamChunk
from app.services.chat_service import get_chat, get_messages, create_message
from app.services.encryption_service import decrypt_key

logger = logging.getLogger(__name__)


async def get_api_key(db: AsyncSession, provider: str) -> Optional[str]:
    """Get and decrypt API key for a provider"""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.provider == provider)
        .where(APIKey.is_active == True)
    )
    api_key_record = result.scalar_one_or_none()
    if not api_key_record:
        logger.warning(f"No active API key found for provider: {provider}")
        return None

    try:
        decrypted_key = decrypt_key(api_key_record.encrypted_key)
        return decrypted_key
    except Exception as e:
        logger.error(f"Failed to decrypt API key for {provider}: {str(e)}")
        return None


def _build_message_history(messages: list[Message], include_reasoning: bool = True) -> list[dict]:
    """
    Build message history for sending to a provider.

    For merged chats, reasoning traces from prior conversations are included
    as part of the assistant message content so the model can "see" the
    thinking that went into previous responses.

    Args:
        messages: List of Message ORM objects
        include_reasoning: Whether to include reasoning traces in the context

    Returns:
        List of message dicts with 'role' and 'content'
    """
    history = []

    for msg in messages:
        if msg.role == "system":
            # System messages are context markers from merges —
            # include them so the model knows which conversation it's reading from
            history.append({"role": "user", "content": f"[System context: {msg.content}]"})
            continue

        content = msg.content

        # For assistant messages with reasoning traces, embed the trace
        # so the model can see its prior thinking when continuing the conversation.
        # This is especially valuable for merged chats where the full context matters.
        if include_reasoning and msg.role == "assistant" and msg.reasoning_trace:
            content = (
                f"<reasoning_trace>\n{msg.reasoning_trace}\n</reasoning_trace>\n\n"
                f"{content}"
            )

        history.append({"role": msg.role, "content": content})

    return history


async def stream_chat_completion(
    db: AsyncSession,
    chat_id: str,
    user_content: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Stream a chat completion and save to database.

    Builds full message history including reasoning traces from prior
    messages, which is critical for merged chats to have full context.

    Args:
        db: Database session
        chat_id: Chat ID
        user_content: User message content
        temperature: Sampling temperature
        max_tokens: Max tokens to generate

    Yields:
        StreamChunk objects
    """
    try:
        # Load chat
        chat = await get_chat(db, chat_id)
        if not chat:
            yield StreamChunk(type="error", data="Chat not found")
            return

        # Get previous messages
        messages = await get_messages(db, chat_id)

        # Build message history with reasoning traces included
        message_history = _build_message_history(messages, include_reasoning=True)

        # Add current user message
        message_history.append({"role": "user", "content": user_content})

        # Save user message to DB
        user_msg = await create_message(db, chat_id, "user", user_content)
        if not user_msg:
            yield StreamChunk(type="error", data="Failed to save user message")
            return

        # Get API key
        api_key = await get_api_key(db, chat.provider)
        if not api_key:
            yield StreamChunk(
                type="error",
                data=f"No API key configured for provider: {chat.provider}"
            )
            return

        # Create provider
        try:
            provider = create_provider(chat.provider, api_key)
        except Exception as e:
            yield StreamChunk(type="error", data=f"Failed to create provider: {str(e)}")
            return

        # Stream completion
        accumulated_content = ""
        accumulated_reasoning = ""

        async for chunk in provider.stream_completion(
            messages=message_history,
            model=chat.model,
            system_prompt=chat.system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.type == "content":
                accumulated_content += chunk.data
                yield chunk
            elif chunk.type == "reasoning":
                accumulated_reasoning += chunk.data
                yield chunk
            elif chunk.type == "error":
                yield chunk
            elif chunk.type == "done":
                # Save assistant message with reasoning trace
                if accumulated_content:
                    assistant_msg = await create_message(
                        db,
                        chat_id,
                        "assistant",
                        accumulated_content,
                        reasoning_trace=accumulated_reasoning if accumulated_reasoning else None
                    )
                    if assistant_msg:
                        logger.info(f"Saved assistant message to chat {chat_id}")
                        yield StreamChunk(type="done", data=assistant_msg.id)
                    else:
                        yield StreamChunk(
                            type="error",
                            data="Failed to save assistant response"
                        )
                else:
                    yield StreamChunk(type="done", data="")

    except Exception as e:
        logger.error(f"Completion streaming error: {str(e)}")
        yield StreamChunk(type="error", data=f"Streaming error: {str(e)}")
