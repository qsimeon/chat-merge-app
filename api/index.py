"""
Vercel serverless entry point for ChatMerge.

This file is the entry point for Vercel Python deployments.
It imports the FastAPI app from the backend and exposes it as the
Vercel handler. Vercel auto-detects FastAPI and handles ASGI.
"""

import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import the FastAPI app
from main import app

# Vercel uses this as the ASGI handler
handler = app
