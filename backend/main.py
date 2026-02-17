import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging

from app.database import create_tables
from app.routes import chats, messages, api_keys, merge, attachments
from app.services import vector_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Chat Merge App",
    description="Multi-provider AI chat with intelligent merge",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
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
    """Create database tables and initialize vector store on startup"""
    logger.info("Creating database tables...")
    await create_tables()
    logger.info("Database tables created successfully")

    # Initialize Pinecone vector store (optional - gracefully skip if not configured)
    try:
        await vector_service.initialize_index()
        logger.info("Vector store initialized")
    except Exception as e:
        logger.warning(f"Vector store initialization skipped (not configured): {e}")
        logger.warning("Set PINECONE_API_KEY to enable RAG retrieval")


@app.get("/health")
async def health_check():
    """Health check endpoint with feature availability"""
    return {
        "status": "ok",
        "vector_store": "enabled" if vector_service.is_configured() else "disabled",
        "rag_enabled": vector_service.is_configured()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
