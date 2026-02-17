import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import async_session
from app.models import Attachment, Message
from app.schemas import AttachmentResponse
from app.services import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["attachments"])

# Allowed file types
ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    # Documents
    "application/pdf",
    "text/plain", "text/markdown", "text/csv",
    # Code files
    "text/html", "text/css", "text/javascript",
    "application/json", "application/xml",
    # Archives
    "application/zip",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def get_db() -> AsyncSession:
    """Get database session"""
    async with async_session() as session:
        yield session


@router.post("/attachments", response_model=List[AttachmentResponse])
async def upload_attachments(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload one or more file attachments (stored locally or in cloud)"""
    try:
        attachments = []

        for file in files:
            # Validate file type
            if file.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type {file.content_type} not allowed"
                )

            # Read file content
            content = await file.read()
            file_size = len(content)

            # Validate file size
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} exceeds max size of 10MB"
                )

            # Save file using storage service (local or cloud)
            storage_path, _ = await storage_service.save_file(
                file_data=content,
                filename=file.filename,
                content_type=file.content_type
            )

            # Create attachment record (message_id will be set later during completion)
            attachment = Attachment(
                message_id="",  # Will be updated when message is created
                file_name=file.filename,
                file_type=file.content_type,
                file_size=file_size,
                storage_path=storage_path
            )
            db.add(attachment)
            attachments.append(attachment)

        await db.commit()

        return [
            AttachmentResponse(
                id=att.id,
                message_id=att.message_id,
                file_name=att.file_name,
                file_type=att.file_type,
                file_size=att.file_size,
                storage_path=att.storage_path,
                created_at=att.created_at.isoformat() if att.created_at else None,
            )
            for att in attachments
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading attachments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload attachments: {str(e)}"
        )


@router.get("/attachments/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Download/retrieve an attachment file"""
    try:
        result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment {attachment_id} not found"
            )

        # If storage path is a cloud URL, redirect to it
        if attachment.storage_path.startswith("http"):
            return RedirectResponse(url=attachment.storage_path)

        # Local file: serve directly
        file_path = Path(attachment.storage_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found"
            )

        return FileResponse(
            path=file_path,
            filename=attachment.file_name,
            media_type=attachment.file_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving attachment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve attachment: {str(e)}"
        )


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an attachment"""
    try:
        result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment {attachment_id} not found"
            )

        # Delete file from storage
        await storage_service.delete_file(attachment.storage_path)

        # Delete database record
        await db.delete(attachment)
        await db.commit()

        return {"status": "deleted", "attachment_id": attachment_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting attachment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete attachment: {str(e)}"
        )
