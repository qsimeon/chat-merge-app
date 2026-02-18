import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.schemas import ChatCreate, ChatResponse, ChatListItem
from app.services.chat_service import (
    create_chat,
    get_chats,
    get_chat,
    update_chat,
    delete_chat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chats", tags=["chats"])


async def get_db() -> AsyncSession:
    """Get database session"""
    async with async_session() as session:
        yield session


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_new_chat(
    chat_data: ChatCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat"""
    try:
        chat = await create_chat(db, chat_data)
        return ChatResponse(
            id=chat.id,
            title=chat.title,
            provider=chat.provider,
            model=chat.model,
            system_prompt=chat.system_prompt,
            is_merged=bool(chat.is_merged),
            created_at=chat.created_at.isoformat() if chat.created_at else None,
            updated_at=chat.updated_at.isoformat() if chat.updated_at else None,
            message_count=0,
            messages=[]
        )
    except Exception as e:
        logger.error(f"Error creating chat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat: {str(e)}"
        )


@router.get("/", response_model=list[ChatListItem])
async def list_chats(db: AsyncSession = Depends(get_db)):
    """Get all chats"""
    try:
        chats = await get_chats(db)
        return [
            ChatListItem(
                id=chat["id"],
                title=chat["title"],
                provider=chat["provider"],
                model=chat["model"],
                is_merged=chat.get("is_merged", False),
                created_at=chat["created_at"],
                updated_at=chat["updated_at"],
                message_count=chat["message_count"],
            )
            for chat in chats
        ]
    except Exception as e:
        logger.error(f"Error listing chats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list chats: {str(e)}"
        )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat_detail(
    chat_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chat with all messages"""
    try:
        chat = await get_chat(db, chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found"
            )

        return ChatResponse(
            id=chat.id,
            title=chat.title,
            provider=chat.provider,
            model=chat.model,
            system_prompt=chat.system_prompt,
            is_merged=bool(chat.is_merged),
            created_at=chat.created_at.isoformat() if chat.created_at else None,
            updated_at=chat.updated_at.isoformat() if chat.updated_at else None,
            message_count=len(chat.messages) if chat.messages else 0,
            messages=[msg.to_dict() for msg in (chat.messages or [])]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat {chat_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat: {str(e)}"
        )


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat_metadata(
    chat_id: str,
    updates: dict,
    db: AsyncSession = Depends(get_db)
):
    """Update chat title or system prompt"""
    try:
        chat = await update_chat(db, chat_id, updates)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found"
            )

        return ChatResponse(
            id=chat.id,
            title=chat.title,
            provider=chat.provider,
            model=chat.model,
            system_prompt=chat.system_prompt,
            is_merged=bool(chat.is_merged),
            created_at=chat.created_at.isoformat() if chat.created_at else None,
            updated_at=chat.updated_at.isoformat() if chat.updated_at else None,
            message_count=len(chat.messages) if chat.messages else 0,
            messages=[msg.to_dict() for msg in (chat.messages or [])]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat {chat_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chat: {str(e)}"
        )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_endpoint(
    chat_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat and all its messages"""
    try:
        success = await delete_chat(db, chat_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat: {str(e)}"
        )
