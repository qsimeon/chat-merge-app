import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.schemas import CompletionRequest, MessageResponse
from app.services.chat_service import get_messages, get_chat
from app.services.completion_service import stream_chat_completion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chats", tags=["messages"])


async def get_db() -> AsyncSession:
    """Get database session"""
    async with async_session() as session:
        yield session


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
async def get_chat_messages(
    chat_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all messages for a chat"""
    try:
        chat = await get_chat(db, chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found"
            )

        messages = await get_messages(db, chat_id)
        return [
            MessageResponse(
                id=msg.id,
                chat_id=msg.chat_id,
                role=msg.role,
                content=msg.content,
                reasoning_trace=msg.reasoning_trace,
                created_at=msg.created_at.isoformat() if msg.created_at else None,
            )
            for msg in messages
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages for chat {chat_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE event string"""
    return f"data: {json.dumps(data)}\n\n"


async def _stream_generator(
    chat_id: str,
    user_content: str,
    temperature: float = 0.7,
    max_tokens: int = None,
):
    """Generator for SSE streaming — creates its own DB session"""
    async with async_session() as db:
        try:
            async for chunk in stream_chat_completion(
                db,
                chat_id,
                user_content,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield _sse_event({
                    "type": chunk.type,
                    "data": chunk.data,
                })
        except Exception as e:
            logger.error(f"Stream generator error: {str(e)}")
            yield _sse_event({
                "type": "error",
                "data": f"Streaming error: {str(e)}",
            })


@router.post("/{chat_id}/completions")
async def stream_completion(
    chat_id: str,
    request: CompletionRequest,
):
    """Stream chat completion using Server-Sent Events"""
    # Verify chat exists using a quick session
    async with async_session() as db:
        chat = await get_chat(db, chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found"
            )

    # Return SSE stream — generator manages its own DB session
    return StreamingResponse(
        _stream_generator(
            chat_id,
            request.content,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
