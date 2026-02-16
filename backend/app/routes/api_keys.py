import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import async_session
from app.models import APIKey
from app.schemas import APIKeyCreate, APIKeyResponse
from app.services.encryption_service import encrypt_key, decrypt_key
from app.providers.factory import create_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


async def get_db() -> AsyncSession:
    """Get database session"""
    async with async_session() as session:
        yield session


@router.post("/", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def store_api_key(
    key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Store/update an API key (encrypted)"""
    try:
        # Check if key already exists
        result = await db.execute(
            select(APIKey).where(APIKey.provider == key_data.provider)
        )
        existing_key = result.scalar_one_or_none()

        # Encrypt the key
        try:
            encrypted_key = encrypt_key(key_data.api_key)
        except Exception as e:
            logger.error(f"Failed to encrypt API key: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encrypt API key"
            )

        if existing_key:
            # Update existing key
            existing_key.encrypted_key = encrypted_key
            existing_key.is_active = True
            db.add(existing_key)
            await db.commit()
            await db.refresh(existing_key)
            logger.info(f"Updated API key for provider {key_data.provider}")
            return APIKeyResponse(
                id=existing_key.id,
                provider=existing_key.provider,
                is_active=existing_key.is_active,
                created_at=existing_key.created_at.isoformat() if existing_key.created_at else None,
            )
        else:
            # Create new key
            new_key = APIKey(
                provider=key_data.provider,
                encrypted_key=encrypted_key,
                is_active=True,
            )
            db.add(new_key)
            await db.commit()
            await db.refresh(new_key)
            logger.info(f"Stored API key for provider {key_data.provider}")
            return APIKeyResponse(
                id=new_key.id,
                provider=new_key.provider,
                is_active=new_key.is_active,
                created_at=new_key.created_at.isoformat() if new_key.created_at else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store API key: {str(e)}"
        )


@router.get("/", response_model=list[APIKeyResponse])
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    """List all stored API keys (without the keys themselves)"""
    try:
        result = await db.execute(select(APIKey))
        keys = result.scalars().all()
        return [
            APIKeyResponse(
                id=key.id,
                provider=key.provider,
                is_active=key.is_active,
                created_at=key.created_at.isoformat() if key.created_at else None,
            )
            for key in keys
        ]
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an API key"""
    try:
        result = await db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        key = result.scalar_one_or_none()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key {key_id} not found"
            )

        await db.delete(key)
        await db.commit()
        logger.info(f"Deleted API key {key_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API key: {str(e)}"
        )


@router.post("/validate")
async def validate_api_key(
    key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Validate that an API key works with the provider"""
    try:
        # Try to create provider and make a simple call
        try:
            provider = create_provider(key_data.provider, key_data.api_key)
            # For now, just check that we can instantiate the provider
            # In a real app, you might make a test API call
            models = provider.get_available_models()
            return {
                "valid": True,
                "provider": key_data.provider,
                "available_models": models
            }
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {key_data.provider}"
            )
        except Exception as e:
            logger.error(f"Failed to validate API key: {str(e)}")
            return {
                "valid": False,
                "provider": key_data.provider,
                "error": str(e)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate API key: {str(e)}"
        )
