"""
Storage service for file attachments.

Saves files to the local filesystem (backend/uploads/).
On Railway, mount a persistent volume at /app/backend/uploads so files
survive redeployments.
"""

import logging
import os
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

LOCAL_UPLOAD_DIR = Path("uploads")


async def save_file(
    file_data: bytes,
    filename: str,
    content_type: str
) -> Tuple[str, str]:
    """
    Save a file to local storage.

    Returns:
        Tuple of (storage_path, public_url)
    """
    return await _save_to_local(file_data, filename)


async def _save_to_local(file_data: bytes, filename: str) -> Tuple[str, str]:
    """Save file to local filesystem"""
    LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)

    file_ext = Path(filename).suffix
    unique_filename = f"{uuid4()}{file_ext}"
    storage_path = str(LOCAL_UPLOAD_DIR / unique_filename)

    async with aiofiles.open(storage_path, 'wb') as f:
        await f.write(file_data)

    logger.info(f"Saved file locally: {storage_path}")
    return storage_path, f"/api/attachments/file/{Path(storage_path).name}"


async def get_file(storage_path: str) -> Optional[bytes]:
    """
    Read a file from local storage.

    Args:
        storage_path: Path returned by save_file()

    Returns:
        File bytes or None if not found
    """
    return await _get_from_local(storage_path)


async def _get_from_local(path: str) -> Optional[bytes]:
    """Read file from local filesystem"""
    file_path = Path(path)
    if not file_path.exists():
        logger.warning(f"Local file not found: {path}")
        return None

    async with aiofiles.open(file_path, 'rb') as f:
        return await f.read()


async def delete_file(storage_path: str) -> bool:
    """
    Delete a file from local storage.

    Returns:
        True if deleted, False otherwise
    """
    return _delete_from_local(storage_path)


def _delete_from_local(path: str) -> bool:
    """Delete file from local filesystem"""
    file_path = Path(path)
    if file_path.exists():
        file_path.unlink()
        return True
    return False
