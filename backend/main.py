import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging

from app.database import create_tables
from app.routes import chats, messages, merge, attachments

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup lifecycle: create DB tables. Vector store initializes lazily on first use."""
    logger.info("Creating database tables...")
    await create_tables()
    logger.info("Database tables created successfully")
    yield


# Create FastAPI app
app = FastAPI(
    title="Chat Merge App",
    description="Multi-provider AI chat with intelligent merge",
    version="1.0.0",
    lifespan=lifespan,
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


@app.get("/health")
async def health_check():
    """Health check. RAG readiness is determined client-side from localStorage keys."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
