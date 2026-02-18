import logging
import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime

from app.models import Chat, Message
from app.schemas import ChatCreate

logger = logging.getLogger(__name__)


async def create_chat(
    db: AsyncSession,
    chat_data: ChatCreate
) -> Chat:
    """Create a new chat"""
    chat = Chat(
        title=chat_data.title,
        provider=chat_data.provider,
        model=chat_data.model,
        system_prompt=chat_data.system_prompt,
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    logger.info(f"Created chat {chat.id} with provider {chat.provider}")
    return chat


async def get_chats(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get all chats with message counts"""
    result = await db.execute(select(Chat).order_by(Chat.created_at.desc()))
    chats = result.scalars().all()
    return [chat.to_dict() for chat in chats]


async def get_chat(db: AsyncSession, chat_id: str) -> Optional[Chat]:
    """Get a specific chat with all its messages"""
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = result.scalar_one_or_none()
    return chat


async def update_chat(
    db: AsyncSession,
    chat_id: str,
    updates: Dict[str, Any]
) -> Optional[Chat]:
    """Update chat metadata"""
    chat = await get_chat(db, chat_id)
    if not chat:
        return None

    # Update allowed fields
    if "title" in updates:
        chat.title = updates["title"]
    if "system_prompt" in updates:
        chat.system_prompt = updates["system_prompt"]

    chat.updated_at = datetime.utcnow()
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    logger.info(f"Updated chat {chat_id}")
    return chat


async def delete_chat(db: AsyncSession, chat_id: str) -> bool:
    """Delete a chat and all its messages, including vector store namespace"""
    from app.services import vector_service
    from app.services.completion_service import _get_rag_keys

    chat = await get_chat(db, chat_id)
    if not chat:
        return False

    # Delete vector namespace (fire and forget — needs Pinecone key from DB)
    pinecone_key, _ = await _get_rag_keys(db)
    if pinecone_key:
        asyncio.create_task(vector_service.delete_namespace(chat_id, pinecone_key))

    await db.delete(chat)
    await db.commit()
    logger.info(f"Deleted chat {chat_id}")
    return True


async def get_messages(db: AsyncSession, chat_id: str) -> List[Message]:
    """Get all messages for a chat"""
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


async def create_message(
    db: AsyncSession,
    chat_id: str,
    role: str,
    content: str,
) -> Optional[Message]:
    """Create a message in a chat"""
    # Verify chat exists
    chat = await get_chat(db, chat_id)
    if not chat:
        logger.warning(f"Chat {chat_id} not found")
        return None

    message = Message(
        chat_id=chat_id,
        role=role,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    logger.info(f"Created message {message.id} in chat {chat_id}")
    return message
