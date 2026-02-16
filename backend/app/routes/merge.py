import logging
import json
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.database import async_session
from app.schemas import MergeRequest, MergeResponse, ModelsResponse
from app.services.merge_service import merge_chats
from app.providers.factory import get_all_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["merge"])


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE event string"""
    return f"data: {json.dumps(data)}\n\n"


async def _merge_stream_generator(merge_request: MergeRequest):
    """Generator for merge SSE streaming — creates its own DB session"""
    async with async_session() as db:
        try:
            async for chunk in merge_chats(
                db,
                merge_request.chat_ids,
                merge_request.merge_provider,
                merge_request.merge_model,
            ):
                yield _sse_event({
                    "type": chunk.type,
                    "data": chunk.data,
                })
        except Exception as e:
            logger.error(f"Merge stream error: {str(e)}")
            yield _sse_event({
                "type": "error",
                "data": f"Merge streaming error: {str(e)}",
            })


@router.post("/merge")
async def merge_conversations(merge_request: MergeRequest):
    """Merge multiple chats into one using intelligent synthesis"""
    if len(merge_request.chat_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 chat IDs required for merge"
        )

    return StreamingResponse(
        _merge_stream_generator(merge_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/models", response_model=ModelsResponse)
async def get_available_models():
    """Get all available models per provider"""
    try:
        models = get_all_models()
        return ModelsResponse(
            openai=models.get("openai", []),
            anthropic=models.get("anthropic", []),
            gemini=models.get("gemini", []),
        )
    except Exception as e:
        logger.error(f"Error getting models: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get models: {str(e)}"
        )
