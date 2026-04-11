# Project Status — ChatMerge
> Last reviewed: 2026-04-10
> Reviewed by: Claude (deep scan)

## Project Overview

ChatMerge is a multi-provider AI chat app (OpenAI, Anthropic, Gemini) whose core feature is **vector-fusion conversation merging**: merged chats fuse their Pinecone vector namespaces via nearest-neighbor averaging, and all context is delivered via RAG — no message copying, no context-window blowup. API keys are browser-side (localStorage → request headers). Live at Railway.

**Live URL**: `https://chat-merge-app-production.up.railway.app`

## Architecture

```
+-----------------------------------------------------------------+
|                    Browser (React 18)                            |
|  localStorage keys -> request headers on streaming calls         |
|  Zustand store --- api.ts --- SSE streaming --- dark theme UI    |
+----------------------------+------------------------------------+
                             | HTTP / SSE (keys in headers)
                             v
+-----------------------------------------------------------------+
|                     FastAPI (Python 3.11)                         |
|                                                                   |
|  Routes                    Services                               |
|  +-- /api/chats           +-- chat_service      (CRUD)           |
|  +-- /api/chats/{id}/     +-- completion_service (streaming +    |
|  |   completions          |                      merged-chat RAG)|
|  +-- /api/merge           +-- merge_service      (vector fusion) |
|  +-- /api/attachments     +-- vector_service     (Pinecone ops)  |
|  +-- /api/models          +-- storage_service    (local files)   |
|  +-- /health                                                      |
+-----------+-----------------------------+-------------------------+
            |                             |
            v                             v
   +-----------------+       +-----------------------+
   |  SQLite / PG    |       |  Pinecone Serverless   |
   |  (SQLAlchemy)   |       |  768-dim, 1 namespace  |
   |                 |       |  per chat              |
   |  Chat, Message, |       |  OpenAI or Gemini emb. |
   |  Attachment,    |       |  fuse_namespaces() for |
   |  MergeHistory   |       |  merged chats          |
   +-----------------+       +-----------------------+
```

## Progress Summary

| Area | Status | Notes |
|------|--------|-------|
| Multi-provider chat (OpenAI / Anthropic / Gemini) | ✅ | All 3 providers stream correctly |
| File & image uploads | ✅ | Drag-drop/paste; images sent to provider vision APIs |
| Vector-fusion merge | ✅ | `fuse_namespaces()` nearest-neighbor + averaging |
| Gemini embedding fallback | ✅ | RAG works with Pinecone + Gemini (no OpenAI required) |
| Merged-chat RAG context | ✅ | `is_merged` flag, always-RAG path in completion_service |
| Client-side API key storage | ✅ | Keys in localStorage, sent as headers — never server-side |
| Image memory in RAG | ✅ | `has_image` metadata + text annotation in embeddings |
| RAG warning UI | ✅ | Merge modal warns when embedding key missing |
| Settings modal Pinecone note | ✅ | Inline note explains embedding key dependency |
| Railway deployment | ✅ | Dockerfile builder, PostgreSQL plugin wired |
| Playwright test suite | 🔧 | 9/9 tests were passing; need re-run after client-side key refactor |
| Railway auto-deploy | 👤 | GitHub App permissions issue — manual fix needed |
| Persistent file uploads | 👤 | Mount Railway volume at `/app/backend/uploads` |

## Embedding Fix History (important for debugging)

The Gemini embedding stack required 3 fixes to get working:
1. **Model name**: `"models/text-embedding-004"` → `"text-embedding-004"` (SDK auto-prepends `models/`)
2. **Response parsing**: `result.embedding.values` → `result.embeddings[0].values` (plural list)
3. **API version**: `v1beta` → `v1` (chat uses v1beta; `text-embedding-004` only on stable v1)

## Current Model Lists

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o4-mini, o3, o3-mini |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5-20251001 |
| Gemini | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash |

Embedding: `text-embedding-3-small` (OpenAI, 768-dim with reduction) or `text-embedding-004` (Gemini v1, 768-dim)

## What's Left

### Human Action Needed
- **Fix Railway auto-deploy** — GitHub App permissions; go to github.com → Settings → Applications → Railway → Configure → add `qsimeon/chat-merge-app`
- **Mount Railway volume** at `/app/backend/uploads` (service → Settings → Volumes) for file upload durability across redeploys
- **Verify Pinecone** — After `v1` API fix, confirm vectors are being stored by checking Pinecone console after sending a message

### Claude Can Handle
- Run Playwright tests after client-side key refactor (may need selector updates for settings modal)
- VectorStore ABC abstraction in `vector_service.py` — makes swapping Pinecone easier

## Cleanup Completed (this session)

- Removed `api_keys.py` route (server-side key storage deleted)
- Removed `encryption_service.py` (Fernet encryption deleted)
- Removed `APIKey` DB model
- Updated all 6 docs (`README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `QUICKSTART.md`, `.env.example`, `STATUS.md`) to remove stale encryption/key references
- Fixed `Sidebar.tsx` hardcoded `'openai'` default (now uses first available LLM provider)
- Fixed `MergeModal.tsx` hardcoded `'openai'` default (same fix)
- Updated all model lists to current: Gemini 2.5, Claude 4.6, OpenAI o4-mini/o3

## Deployment Reference

**Stack**: Dockerfile → Python 3.11-slim + Node 20 → builds React dist → uv sync → uvicorn `--proxy-headers`

**Required Railway env vars**: `DATABASE_URL` (auto-injected by PostgreSQL plugin), `ALLOWED_ORIGINS`

**Not needed anymore**: `FERNET_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `PINECONE_API_KEY` (all browser-side)
