import logging
import asyncio
import base64
from pathlib import Path
from typing import AsyncGenerator, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Chat, Message, APIKey, Attachment
from app.providers.factory import create_provider
from app.providers.base import StreamChunk
from app.services.chat_service import get_chat, get_messages, create_message
from app.services.encryption_service import decrypt_key
from app.services import vector_service, storage_service

logger = logging.getLogger(__name__)

# RAG configuration
USE_RAG = True  # Enable/disable RAG retrieval
RAG_CONTEXT_LIMIT = 8  # Number of relevant messages to retrieve
RECENT_MESSAGES_LIMIT = 10  # Always include N most recent messages


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


async def _load_attachment_data(attachment: Attachment) -> Optional[dict]:
    """Load attachment file data and encode as base64 (supports local + cloud storage)"""
    try:
        file_data = await storage_service.get_file(attachment.storage_path)
        if not file_data:
            logger.warning(f"Attachment file not found: {attachment.storage_path}")
            return None

        base64_data = base64.b64encode(file_data).decode('utf-8')

        return {
            "id": attachment.id,
            "file_name": attachment.file_name,
            "file_type": attachment.file_type,
            "file_size": attachment.file_size,
            "data": base64_data
        }
    except Exception as e:
        logger.error(f"Error loading attachment {attachment.id}: {str(e)}")
        return None


async def _build_message_history(messages: list[Message], include_reasoning: bool = True) -> list[dict]:
    """
    Build message history for sending to a provider.

    For merged chats, reasoning traces from prior conversations are included
    as part of the assistant message content so the model can "see" the
    thinking that went into previous responses.

    Args:
        messages: List of Message ORM objects
        include_reasoning: Whether to include reasoning traces in the context

    Returns:
        List of message dicts with 'role', 'content', and optional 'attachments'
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

        msg_dict = {"role": msg.role, "content": content}

        # Load attachments if present
        if msg.attachments:
            attachments_data = []
            for att in msg.attachments:
                att_data = await _load_attachment_data(att)
                if att_data:
                    attachments_data.append(att_data)
            if attachments_data:
                msg_dict["attachments"] = attachments_data

        history.append(msg_dict)

    return history


async def _build_rag_context(
    db: AsyncSession,
    chat_id: str,
    query_text: str,
    recent_messages: List[Message]
) -> List[dict]:
    """
    Build context using RAG retrieval.

    Combines:
    1. Recent messages (for conversation continuity)
    2. Relevant historical messages (via vector similarity search)

    Args:
        db: Database session
        chat_id: Chat ID
        query_text: Query text for retrieval
        recent_messages: Recent messages to always include

    Returns:
        List of message dicts for the LLM
    """
    try:
        # Get relevant messages via vector search
        relevant_context = await vector_service.query_relevant_context(
            chat_id=chat_id,
            query_text=query_text,
            top_k=RAG_CONTEXT_LIMIT
        )

        # Get message IDs that are already in recent messages
        recent_msg_ids = {msg.id for msg in recent_messages}

        # Fetch full message objects for relevant context
        relevant_msg_ids = [
            item["message_id"] for item in relevant_context
            if item["message_id"] not in recent_msg_ids  # Avoid duplicates
        ]

        if relevant_msg_ids:
            result = await db.execute(
                select(Message).where(Message.id.in_(relevant_msg_ids))
            )
            relevant_messages = result.scalars().all()
        else:
            relevant_messages = []

        # Combine: relevant historical messages + recent messages
        # Sort by timestamp to maintain chronological order
        all_messages = list(relevant_messages) + list(recent_messages)
        all_messages.sort(key=lambda m: m.created_at or "")

        # Build message history
        return await _build_message_history(all_messages, include_reasoning=True)

    except Exception as e:
        logger.warning(f"RAG retrieval failed, falling back to recent messages: {e}")
        # Fallback to just recent messages
        return await _build_message_history(recent_messages, include_reasoning=True)


async def stream_chat_completion(
    db: AsyncSession,
    chat_id: str,
    user_content: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    attachment_ids: Optional[List[str]] = None,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Stream a chat completion and save to database.

    Uses RAG retrieval for merged chats to provide relevant context without
    hitting token limits. Falls back to recent messages if RAG is unavailable.

    Args:
        db: Database session
        chat_id: Chat ID
        user_content: User message content
        temperature: Sampling temperature
        max_tokens: Max tokens to generate
        attachment_ids: Optional list of attachment IDs

    Yields:
        StreamChunk objects
    """
    try:
        # Load chat
        chat = await get_chat(db, chat_id)
        if not chat:
            yield StreamChunk(type="error", data="Chat not found")
            return

        # Get previous messages (all or recent based on RAG)
        all_messages = await get_messages(db, chat_id)

        # Save user message to DB first (so we have a message_id for attachments)
        user_msg = await create_message(db, chat_id, "user", user_content)
        if not user_msg:
            yield StreamChunk(type="error", data="Failed to save user message")
            return

        # Handle attachments
        current_attachment_data = []
        if attachment_ids:
            result = await db.execute(
                select(Attachment).where(Attachment.id.in_(attachment_ids))
            )
            attachments = result.scalars().all()
            if attachments:
                # Associate attachments with the new user message
                for att in attachments:
                    att.message_id = user_msg.id
                await db.commit()

                # Load attachment data for API call
                for att in attachments:
                    att_data = _load_attachment_data(att)
                    if att_data:
                        current_attachment_data.append(att_data)

        # Build context using RAG if enabled (for merged chats with many messages)
        if USE_RAG and len(all_messages) > RECENT_MESSAGES_LIMIT:
            # Use recent messages + RAG-retrieved relevant messages
            recent_messages = all_messages[-RECENT_MESSAGES_LIMIT:]
            message_history = await _build_rag_context(
                db, chat_id, user_content, recent_messages
            )
            logger.info(f"Using RAG context for chat {chat_id} ({len(all_messages)} total messages)")
        else:
            # For short conversations, use full history
            message_history = await _build_message_history(all_messages, include_reasoning=True)

        # Store user message vector (fire and forget)
        asyncio.create_task(vector_service.store_message_vector(
            chat_id=chat_id,
            message_id=user_msg.id,
            content=user_content,
            role="user",
            attachments=[{"file_name": a["file_name"]} for a in current_attachment_data] if current_attachment_data else None
        ))

        # Add current user message to history
        current_msg_dict = {"role": "user", "content": user_content}
        if current_attachment_data:
            current_msg_dict["attachments"] = current_attachment_data
        message_history.append(current_msg_dict)

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

                        # Store assistant message vector (fire and forget)
                        asyncio.create_task(vector_service.store_message_vector(
                            chat_id=chat_id,
                            message_id=assistant_msg.id,
                            content=accumulated_content,
                            role="assistant",
                            reasoning_trace=accumulated_reasoning if accumulated_reasoning else None
                        ))

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
