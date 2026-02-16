import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import logging

logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = "sqlite+aiosqlite:///./chat_app.db"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 30}
)

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
    """Create all database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created")
