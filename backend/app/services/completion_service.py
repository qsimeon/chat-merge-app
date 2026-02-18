import logging
import asyncio
import base64
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

USE_RAG = True
RAG_CONTEXT_LIMIT = 8
RECENT_MESSAGES_LIMIT = 10


async def get_api_key(db: AsyncSession, provider: str) -> Optional[str]:
    """Get and decrypt API key for a provider."""
    result = await db.execute(
        select(APIKey).where(APIKey.provider == provider).where(APIKey.is_active == True)
    )
    record = result.scalar_one_or_none()
    if not record:
        logger.warning(f"No active API key found for provider: {provider}")
        return None
    try:
        return decrypt_key(record.encrypted_key)
    except Exception as e:
        logger.error(f"Failed to decrypt API key for {provider}: {e}")
        return None


async def _load_attachment_data(attachment: Attachment) -> Optional[dict]:
    """Load attachment file and base64-encode it."""
    try:
        file_data = await storage_service.get_file(attachment.storage_path)
        if not file_data:
            logger.warning(f"Attachment file not found: {attachment.storage_path}")
            return None
        return {
            "id": attachment.id,
            "file_name": attachment.file_name,
            "file_type": attachment.file_type,
            "file_size": attachment.file_size,
            "data": base64.b64encode(file_data).decode('utf-8'),
        }
    except Exception as e:
        logger.error(f"Error loading attachment {attachment.id}: {e}")
        return None


async def _build_message_history(messages: list[Message]) -> list[dict]:
    """Convert Message ORM objects to provider-ready message dicts."""
    history = []
    for msg in messages:
        if msg.role == "system":
            history.append({"role": "user", "content": f"[System context: {msg.content}]"})
            continue

        msg_dict = {"role": msg.role, "content": msg.content}

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
    recent_messages: List[Message],
    pinecone_key: str,
    openai_key: str,
) -> List[dict]:
    """RAG context for regular (non-merged) chats: recent messages + vector-retrieved historical messages."""
    try:
        relevant_context = await vector_service.query_relevant_context(
            chat_id=chat_id,
            query_text=query_text,
            pinecone_key=pinecone_key,
            openai_key=openai_key,
            top_k=RAG_CONTEXT_LIMIT,
        )

        if relevant_context:
            logger.info(f"RAG retrieved {len(relevant_context)} messages for chat {chat_id}:")
            for item in relevant_context:
                logger.info(f"  [{item['metadata'].get('role','?')}] score={item['score']:.3f} | {item['metadata'].get('content','')[:80]!r}")
        else:
            logger.warning(f"RAG returned 0 results for chat {chat_id}")

        recent_msg_ids = {msg.id for msg in recent_messages}
        relevant_msg_ids = [
            item["message_id"] for item in relevant_context
            if item["message_id"] not in recent_msg_ids
        ]

        if relevant_msg_ids:
            result = await db.execute(select(Message).where(Message.id.in_(relevant_msg_ids)))
            relevant_messages = result.scalars().all()
        else:
            relevant_messages = []

        all_context = sorted(
            list(relevant_messages) + list(recent_messages),
            key=lambda m: m.created_at or ""
        )
        logger.info(f"RAG context: {len(relevant_messages)} retrieved + {len(recent_messages)} recent = {len(all_context)} total")
        return await _build_message_history(all_context)

    except Exception as e:
        logger.warning(f"RAG retrieval failed, falling back to recent messages: {e}")
        return await _build_message_history(recent_messages)


async def _build_merged_chat_context(
    chat_id: str,
    user_query: str,
    prior_messages: List[Message],
    pinecone_key: str,
    openai_key: str,
) -> tuple[str, List[dict]]:
    """
    Build context for merged chats via the fused RAG namespace.

    Returns (rag_context_block, recent_history):
      - rag_context_block is injected into the dynamic system prompt
      - recent_history covers the AI intro + any exchanges since the merge
    """
    hits = await vector_service.query_relevant_context(
        chat_id=chat_id,
        query_text=user_query,
        pinecone_key=pinecone_key,
        openai_key=openai_key,
        top_k=8,
    )

    if hits:
        logger.info(f"Merged chat RAG: {len(hits)} hits for chat {chat_id}:")
        for hit in hits:
            vec_type = hit["metadata"].get("type", "kept")
            source = hit["metadata"].get("source_chat_id", "?")[:8]
            logger.info(f"  [{vec_type}] score={hit['score']:.3f} src={source} | {hit['metadata'].get('content','')[:80]!r}")
    else:
        logger.warning(f"Merged chat RAG returned 0 hits for chat {chat_id}")

    context_lines = ["[Retrieved context from merged conversations — most relevant to your query]", "---"]
    for hit in hits:
        metadata = hit["metadata"]
        content = metadata.get("content", "")
        if metadata.get("type") == "fused":
            context_lines.append(content)
        else:
            context_lines.append(f"[{metadata.get('role', 'assistant')}]: {content}")
        context_lines.append("---")

    rag_context_block = "\n".join(context_lines) if hits else ""
    recent_history = await _build_message_history(prior_messages)
    return rag_context_block, recent_history


async def _get_rag_keys(db: AsyncSession):
    """Fetch Pinecone and OpenAI keys from DB."""
    return await get_api_key(db, "pinecone"), await get_api_key(db, "openai")


async def stream_chat_completion(
    db: AsyncSession,
    chat_id: str,
    user_content: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    attachment_ids: Optional[List[str]] = None,
) -> AsyncGenerator[StreamChunk, None]:
    """Stream a chat completion, save to DB, and store vectors."""
    try:
        chat = await get_chat(db, chat_id)
        if not chat:
            yield StreamChunk(type="error", data="Chat not found")
            return

        # Snapshot messages before saving the new user message
        all_messages = await get_messages(db, chat_id)

        user_msg = await create_message(db, chat_id, "user", user_content)
        if not user_msg:
            yield StreamChunk(type="error", data="Failed to save user message")
            return

        # Handle attachments
        current_attachment_data = []
        if attachment_ids:
            result = await db.execute(select(Attachment).where(Attachment.id.in_(attachment_ids)))
            attachments = result.scalars().all()
            if attachments:
                for att in attachments:
                    att.message_id = user_msg.id
                await db.commit()
                for att in attachments:
                    att_data = await _load_attachment_data(att)
                    if att_data:
                        current_attachment_data.append(att_data)

        pinecone_key, openai_key = await _get_rag_keys(db)
        rag_available = bool(pinecone_key and openai_key)

        is_merged = bool(chat.is_merged)
        dynamic_system_prompt = chat.system_prompt

        if is_merged:
            if rag_available:
                logger.info(f"Merged chat {chat_id}: building RAG context")
                rag_context_block, message_history = await _build_merged_chat_context(
                    chat_id=chat_id,
                    user_query=user_content,
                    prior_messages=all_messages,
                    pinecone_key=pinecone_key,
                    openai_key=openai_key,
                )
                if rag_context_block:
                    dynamic_system_prompt = ((chat.system_prompt or "") + "\n\n" + rag_context_block).strip()
            else:
                logger.warning(f"Merged chat {chat_id}: RAG keys not configured — using recent messages only")
                message_history = await _build_message_history(all_messages)
        elif USE_RAG and rag_available and len(all_messages) > RECENT_MESSAGES_LIMIT:
            recent_messages = all_messages[-RECENT_MESSAGES_LIMIT:]
            message_history = await _build_rag_context(
                db, chat_id, user_content, recent_messages,
                pinecone_key=pinecone_key, openai_key=openai_key,
            )
            logger.info(f"Using RAG for chat {chat_id} ({len(all_messages)} total messages)")
        else:
            if USE_RAG and len(all_messages) > RECENT_MESSAGES_LIMIT and not rag_available:
                logger.info("RAG skipped: Pinecone or OpenAI key not configured")
            message_history = await _build_message_history(all_messages)

        # Store user message vector (fire and forget)
        if rag_available:
            asyncio.create_task(vector_service.store_message_vector(
                chat_id=chat_id,
                message_id=user_msg.id,
                content=user_content,
                role="user",
                pinecone_key=pinecone_key,
                openai_key=openai_key,
                attachments=[{"file_name": a["file_name"]} for a in current_attachment_data] or None,
            ))

        current_msg_dict = {"role": "user", "content": user_content}
        if current_attachment_data:
            current_msg_dict["attachments"] = current_attachment_data
        message_history.append(current_msg_dict)

        api_key = await get_api_key(db, chat.provider)
        if not api_key:
            yield StreamChunk(type="error", data=f"No API key configured for provider: {chat.provider}")
            return

        try:
            provider = create_provider(chat.provider, api_key)
        except Exception as e:
            yield StreamChunk(type="error", data=f"Failed to create provider: {e}")
            return

        accumulated_content = ""

        async for chunk in provider.stream_completion(
            messages=message_history,
            model=chat.model,
            system_prompt=dynamic_system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.type == "content":
                accumulated_content += chunk.data
                yield chunk
            elif chunk.type == "error":
                yield chunk
            elif chunk.type == "done":
                if accumulated_content:
                    assistant_msg = await create_message(db, chat_id, "assistant", accumulated_content)
                    if assistant_msg:
                        logger.info(f"Saved assistant message to chat {chat_id}")
                        if rag_available:
                            asyncio.create_task(vector_service.store_message_vector(
                                chat_id=chat_id,
                                message_id=assistant_msg.id,
                                content=accumulated_content,
                                role="assistant",
                                pinecone_key=pinecone_key,
                                openai_key=openai_key,
                            ))
                        yield StreamChunk(type="done", data=assistant_msg.id)
                    else:
                        yield StreamChunk(type="error", data="Failed to save assistant response")
                else:
                    yield StreamChunk(type="done", data="")

    except Exception as e:
        logger.error(f"Completion streaming error: {e}")
        yield StreamChunk(type="error", data=f"Streaming error: {e}")
