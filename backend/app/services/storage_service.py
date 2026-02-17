"""
Storage service for file attachments.

Supports two backends:
- Local filesystem (development): files stored in uploads/ directory
- Vercel Blob (production): files stored in cloud, returns blob URLs

Set BLOB_READ_WRITE_TOKEN env var to use Vercel Blob.
Otherwise falls back to local storage.
"""

import logging
import os
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

# Vercel Blob configuration
BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
USE_BLOB_STORAGE = bool(BLOB_TOKEN)

# Local storage configuration
LOCAL_UPLOAD_DIR = Path("uploads")


def is_using_cloud_storage() -> bool:
    """Check if cloud storage (Vercel Blob) is configured"""
    return USE_BLOB_STORAGE


async def save_file(
    file_data: bytes,
    filename: str,
    content_type: str
) -> Tuple[str, str]:
    """
    Save a file to storage.

    Args:
        file_data: Raw file bytes
        filename: Original filename
        content_type: MIME type

    Returns:
        Tuple of (storage_path, public_url)
        - storage_path: Used for local lookups (same as public_url for blob)
        - public_url: URL to access the file
    """
    if USE_BLOB_STORAGE:
        return await _save_to_blob(file_data, filename, content_type)
    else:
        return await _save_to_local(file_data, filename)


async def _save_to_local(file_data: bytes, filename: str) -> Tuple[str, str]:
    """Save file to local filesystem"""
    LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)

    # Generate unique filename to avoid collisions
    file_ext = Path(filename).suffix
    unique_filename = f"{uuid4()}{file_ext}"
    storage_path = str(LOCAL_UPLOAD_DIR / unique_filename)

    async with aiofiles.open(storage_path, 'wb') as f:
        await f.write(file_data)

    logger.info(f"Saved file locally: {storage_path}")
    return storage_path, f"/api/attachments/file/{Path(storage_path).name}"


async def _save_to_blob(
    file_data: bytes,
    filename: str,
    content_type: str
) -> Tuple[str, str]:
    """Save file to Vercel Blob storage"""
    import httpx

    # Generate unique blob path
    file_ext = Path(filename).suffix
    blob_path = f"attachments/{uuid4()}{file_ext}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"https://blob.vercel-storage.com/{blob_path}",
                content=file_data,
                headers={
                    "Authorization": f"Bearer {BLOB_TOKEN}",
                    "Content-Type": content_type,
                    "X-Content-Type": content_type,
                }
            )
            response.raise_for_status()
            blob_data = response.json()

        blob_url = blob_data.get("url", "")
        logger.info(f"Saved file to Vercel Blob: {blob_url}")
        return blob_url, blob_url  # Both path and URL are the blob URL

    except Exception as e:
        logger.error(f"Failed to save to Vercel Blob: {e}")
        raise


async def get_file(storage_path: str) -> Optional[bytes]:
    """
    Read a file from storage.

    Args:
        storage_path: Path or URL from save_file()

    Returns:
        File bytes or None if not found
    """
    if storage_path.startswith("http"):
        return await _get_from_blob(storage_path)
    else:
        return await _get_from_local(storage_path)


async def _get_from_local(path: str) -> Optional[bytes]:
    """Read file from local filesystem"""
    file_path = Path(path)
    if not file_path.exists():
        logger.warning(f"Local file not found: {path}")
        return None

    async with aiofiles.open(file_path, 'rb') as f:
        return await f.read()


async def _get_from_blob(url: str) -> Optional[bytes]:
    """Download file from Vercel Blob"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Failed to fetch from blob: {e}")
        return None


async def delete_file(storage_path: str) -> bool:
    """
    Delete a file from storage.

    Args:
        storage_path: Path or URL from save_file()

    Returns:
        True if deleted, False otherwise
    """
    if storage_path.startswith("http"):
        return await _delete_from_blob(storage_path)
    else:
        return _delete_from_local(storage_path)


def _delete_from_local(path: str) -> bool:
    """Delete file from local filesystem"""
    file_path = Path(path)
    if file_path.exists():
        file_path.unlink()
        return True
    return False


async def _delete_from_blob(url: str) -> bool:
    """Delete file from Vercel Blob"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                "https://blob.vercel-storage.com/delete",
                headers={"Authorization": f"Bearer {BLOB_TOKEN}"},
                json={"urls": [url]}
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to delete from blob: {e}")
        return False
