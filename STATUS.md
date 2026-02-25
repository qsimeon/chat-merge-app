# Project Status — ChatMerge
> Last reviewed: 2026-02-24
> Reviewed by: Claude (deep scan)

## Project Overview

ChatMerge is a multi-provider AI chat app (OpenAI, Anthropic, Gemini) whose core innovation is **vector-fusion conversation merging**: merged chats fuse their Pinecone vector namespaces via nearest-neighbor averaging, and all context in the merged chat is delivered via RAG — no message copying, no context-window blowup. Users supply their own API keys. The app is live at [chat-merge-app-production.up.railway.app](https://chat-merge-app-production.up.railway.app).

## Progress Summary

| Area | Status | Notes |
|------|--------|-------|
| Multi-provider chat (OpenAI / Anthropic / Gemini) | ✅ | All 3 providers stream correctly |
| File & image uploads | ✅ | Drag-drop/paste; images sent to provider vision APIs |
| Vector-fusion merge | ✅ | `fuse_namespaces()` nearest-neighbor + averaging |
| Merged-chat RAG context | ✅ | `is_merged` flag, always-RAG path in completion_service |
| Encrypted API key storage | ✅ | Fernet encryption |
| Error message display | ✅ | Fixed: error no longer silently wiped after sendMessage |
| Onboarding CTA (landing page) | ✅ | "Get started in 2 steps" guide for new users |
| Railway deployment | ✅ | Live — Dockerfile builder, PostgreSQL plugin wired |
| Railway auto-deploy | 👤 | GitHub App permissions issue — manual fix needed |
| Playwright test suite (local) | ✅ | 9/9 passing |
| Documentation | ✅ | All Vercel refs removed; Railway is sole deploy target |
| File uploads in production | 👤 | Uploads reset on redeploy until persistent volume is mounted |
| Auth / multi-user | ❓ | Intentionally absent for v1 demo |

## What's Complete

The core product is **feature-complete for v1**:
- All three LLM providers work with streaming SSE
- File/image uploads with vision API support
- Vector-fusion merge algorithm implemented and tested
- Merged chats use RAG exclusively (zero context-window blowup)
- Clean dark-themed UI with onboarding guide for new users
- Full Playwright test suite (9/9 local)
- Deployed to Railway with PostgreSQL; HTTPS works correctly

## What's Left

### Human Action Needed
- **Fix Railway auto-deploy** — GitHub App permissions broke during setup. Fix:
  1. github.com → Settings → Applications → Railway → Configure
  2. Add `qsimeon/chat-merge-app` to the allowed repositories list
  3. Back in Railway → your service → Settings → Source → reconnect
- **Persistent file uploads** — Mount a Railway volume at `/app/backend/uploads` (service → Settings → Volumes). Without it, uploaded files vanish on each redeploy. For a no-uploads demo this is fine; for real use it matters.
- **Verify production CTA** — Just pushed the "Get started in 2 steps" landing-page update. Trigger a manual Railway redeploy (until auto-deploy is fixed), then confirm it renders correctly.
- **Pinecone in production** — The Pinecone index must be manually created or exist before a user adds a Pinecone API key. The app creates it lazily on first use, which may timeout on cold start. Consider pre-creating index `chatmerge` (dimension 1536, cosine, us-east-1) or documenting this for users.

### Claude Can Handle
- **`@app.on_event("startup")` deprecation** (`backend/main.py:63`) — FastAPI 0.100+ prefers the `lifespan` context manager. Not broken, but flagged as deprecated in FastAPI logs.
- **`pyproject.toml` readme stale ref** (`backend/pyproject.toml:5`) — `readme = "README.md"` points to `backend/README.md` which was deleted. Low impact (just a metadata warning) but easy to fix by removing that line.
- **`backend/requirements.txt` redundancy** — Duplicates `pyproject.toml`. Only kept for `start.sh`'s pip fallback path. Could be removed if `start.sh` is simplified to require uv (which is already the default).
- **VectorStore abstraction** — Extract a `VectorStore` ABC from `vector_service.py`; add `PineconeVectorStore` implementation. Makes swapping to Qdrant/Weaviate/Chroma trivial.

## Cleanup Recommendations

### Safe to Delete (with confirmation)
- `backend/requirements.txt` — Exact duplicate of `pyproject.toml` deps. `start.sh` uses it as a fallback only if uv isn't present; since uv ships in the Dockerfile and is standard for this project, this file is maintenance overhead. Delete if `start.sh`'s pip fallback branch is also removed.

### Should Update
- `backend/pyproject.toml:5` — `readme = "README.md"` → remove this line (backend/README.md no longer exists)
- `backend/main.py:63` — `@app.on_event("startup")` → migrate to `lifespan` context manager to silence FastAPI deprecation warnings

### Not a Problem (verified)
- `.aqe/` files — gitignored, not tracked
- `backend/chat_app.db`, `.encryption_key` — gitignored, not tracked
- `frontend/dist/` — gitignored, built by Dockerfile
- `backend/__pycache__/` — gitignored, not tracked

## Deployment Reference

**Live URL**: `https://chat-merge-app-production.up.railway.app`

**Stack**: Dockerfile builder → Python 3.11-slim + Node 20 → builds React dist → uv sync → uvicorn with `--proxy-headers`

**Required env vars on Railway**:
- `DATABASE_URL` — auto-injected by Railway PostgreSQL plugin
- `ALLOWED_ORIGINS` — set to `https://chat-merge-app-production.up.railway.app`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `PINECONE_API_KEY` — user-supplied at runtime via Settings modal (stored encrypted in DB), OR set as Railway env vars for a pre-configured demo

## Recommendations for Next Session

1. **Fix Railway auto-deploy** (human) — 5-minute GitHub App permissions fix unlocks push-to-deploy
2. **Migrate `@app.on_event` → `lifespan`** (Claude) — silence FastAPI deprecation warnings, future-proof startup logic
3. **Remove `backend/requirements.txt`** (Claude, with confirmation) — clean up the one redundant file remaining from the Vercel era
