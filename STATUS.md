# Project Status — ChatMerge
> Last reviewed: 2026-02-24
> Reviewed by: Claude (deep scan)

## Project Overview

ChatMerge is a multi-provider AI chat application (OpenAI, Anthropic, Gemini) whose core innovation is **vector-fusion conversation merging**: when two chats are merged, their Pinecone vector namespaces are intelligently fused using nearest-neighbor averaging. The merged chat has zero copied messages — context comes entirely from RAG retrieval against the fused vector store. Demo app, users supply their own API keys.

## Progress Summary

| Area | Status | Notes |
|------|--------|-------|
| Multi-provider chat (OpenAI/Anthropic/Gemini) | ✅ | All 3 streaming correctly |
| File & image uploads | ✅ | Drag-drop/paste; images sent to provider vision APIs |
| Vector-fusion merge | ✅ | fuse_namespaces() with numpy cosine NN + averaging |
| Merged-chat RAG context | ✅ | is_merged flag, always-RAG path in completion_service |
| Encrypted API key storage | ✅ | Fernet encryption |
| Attachment persistence in chat history | ✅ | Fixed in latest session |
| Provider dropdown cleanup (no Pinecone in LLM lists) | ✅ | Uses LLM_PROVIDER_LABELS |
| Merged chat reply on Gemini/Anthropic | ✅ | Leading non-user message strip |
| Playwright test suite | ✅ | 9/9 passing |
| Documentation | ✅ | README, AGENTS.md, ARCHITECTURE.md, QUICKSTART.md updated; redundant backend/README.md + frontend/README.md + LATEST_PLAN.md deleted |
| Railway deployment config | ✅ | `railway.toml` added at repo root; `start.sh` updated to use `uv` |
| Deployment (live) | ⏳ | Awaiting human: create Railway account, add PostgreSQL plugin, set ALLOWED_ORIGINS |
| Vector store abstraction (swappable backend) | ⏳ | Pinecone-specific; modular VectorStore ABC would unlock alternatives |
| Auth / multi-user | ❓ | Currently single-user, no auth — intentional for demo |

## What's Complete

The core product is feature-complete for a v1 demo:
- All three LLM providers work with streaming SSE
- File/image uploads work, attachments persist across navigation
- The vector-fusion merge algorithm is implemented and tested
- Merged chats use RAG exclusively (no context window bombs)
- The dark-themed UI is clean and functional
- 9/9 Playwright tests pass with zero console errors
- All docs reflect the current architecture

## What's Left

### Claude Can Handle
- **Vector store abstraction** — extract a `VectorStore` ABC from `vector_service.py`; add `PineconeVectorStore` implementation; makes swapping to Qdrant/Weaviate/Chroma trivial

### Human Action Needed
- **Deploy to Railway** — `railway.toml` is ready; requires creating a Railway account, adding the PostgreSQL plugin, and setting the `ALLOWED_ORIGINS` env var to the deployed frontend URL
- **Create a Pinecone index** named `chatmerge` (dimension 1536, cosine metric, us-east-1) before deploying — currently auto-created on first use but may timeout on cold start
- **File storage in production** — local `uploads/` won't persist on Railway unless a persistent volume is attached; alternatively use Vercel Blob or S3

### Needs Clarification
- **Auth**: Is no-auth intentional long-term, or do you want basic auth before sharing publicly?
- **File uploads in prod**: Keep local uploads (works on Railway/Render with a persistent volume), or move to cloud storage (required for Vercel/serverless)?

## Cleanup Recommendations

### Code to Clean Up
- `vector_service.py:merge_vector_namespaces()` — still used as fallback in merge_service; keep it, but it's now an implementation detail (not the primary path)

## Deployment Recommendation

See the in-chat discussion for full analysis. Short version:

**Recommended: Railway**
- Supports persistent Python processes → SSE streaming works without timeout risk
- GitHub push-to-deploy
- PostgreSQL plugin (add-on, free tier available)
- One service hosts both backend + frontend dist
- Change: `DATABASE_URL` env var → auto-switches SQLite → PostgreSQL

**Vercel (already partially set up)** is viable but has a **60s SSE timeout** on Pro (10s on Hobby). Long AI responses WILL timeout. It's also stateless — needs Blob storage for file uploads.

**Render** is another solid Railway alternative with very similar tradeoffs.

## Recommendations for Next Session

1. **Deploy to Railway**: `railway.toml` is ready — create account, add PostgreSQL plugin, set `ALLOWED_ORIGINS`, push
2. **Add VectorStore abstraction**: 2-3 hour refactor that makes the codebase clean and future-proof against vector DB vendor changes
