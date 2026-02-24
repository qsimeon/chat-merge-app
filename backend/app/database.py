import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Determine database URL from environment
# - Local development: SQLite via aiosqlite
# - Production (Railway): PostgreSQL via asyncpg (Railway injects DATABASE_URL automatically)
_raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./chat_app.db")

# Railway / Heroku provide postgres:// URLs — upgrade to asyncpg dialect
if _raw_url.startswith("postgres://"):
    DATABASE_URL = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql://"):
    DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = _raw_url

IS_SQLITE = DATABASE_URL.startswith("sqlite")
logger.info(f"Using {'SQLite' if IS_SQLITE else 'PostgreSQL'} database")

# Build engine kwargs
engine_kwargs = {
    "echo": False,
    "future": True,
}

if IS_SQLITE:
    engine_kwargs["connect_args"] = {"timeout": 30}

# Create async engine
engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True
)

# Base class for models
Base = declarative_base()


async def get_session() -> AsyncSession:
    """Get a database session"""
    async with async_session() as session:
        yield session


async def create_tables():
    """Create all database tables and run migrations for new columns."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add is_merged column if it doesn't exist yet (existing databases)
        try:
            if IS_SQLITE:
                await conn.execute(text("ALTER TABLE chats ADD COLUMN is_merged BOOLEAN DEFAULT 0"))
            else:
                await conn.execute(text("ALTER TABLE chats ADD COLUMN is_merged BOOLEAN DEFAULT FALSE"))
            logger.info("Migration: added is_merged column to chats table")
        except Exception:
            pass  # Column already exists
    logger.info("All database tables created")
