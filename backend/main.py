import os
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import create_tables, async_session
from app.routes import chats, messages, api_keys, merge, attachments

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Chat Merge App",
    description="Multi-provider AI chat with intelligent merge",
    version="1.0.0"
)

# CORS configuration
# In production, set ALLOWED_ORIGINS env var to your actual domain
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _origins_env:
    ALLOWED_ORIGINS = [origin.strip() for origin in _origins_env.split(",")]
else:
    # Development: allow all origins
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(api_keys.router)
app.include_router(merge.router)
app.include_router(attachments.router)

# Static files setup
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/")
async def root():
    """Serve the frontend index.html"""
    frontend_index = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        return FileResponse(frontend_index)
    return {"message": "Chat Merge App API. Frontend not found."}


@app.on_event("startup")
async def startup_event():
    """Create database tables on startup. Vector store initializes lazily on first use."""
    logger.info("Creating database tables...")
    await create_tables()
    logger.info("Database tables created successfully")


@app.get("/health")
async def health_check():
    """Health check — RAG status reflects whether user has saved a Pinecone key."""
    from app.services.completion_service import _get_rag_keys
    try:
        async with async_session() as db:
            pinecone_key, openai_key = await _get_rag_keys(db)
            rag_ready = bool(pinecone_key and openai_key)
    except Exception:
        rag_ready = False
    return {
        "status": "ok",
        "vector_store": "enabled" if rag_ready else "disabled",
        "rag_enabled": rag_ready,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
