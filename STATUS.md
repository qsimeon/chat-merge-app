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
| FastAPI lifespan migration | ✅ | `@app.on_event("startup")` → `lifespan` context manager |
| `pyproject.toml` readme ref | ✅ | Stale `readme = "README.md"` line removed |
| Fernet key stability (production) | ✅ | `encryption_service` now reads `FERNET_KEY` env var first |
| Security audit | ✅ | No hardcoded secrets, no leaked keys, gitignore verified |
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
- FastAPI startup uses modern `lifespan` context manager (no deprecation warnings)

## What's Left

### Human Action Needed
- **Set `FERNET_KEY` on Railway** (CRITICAL — do this now) — Without it every redeploy generates a new Fernet key, silently making all stored API keys unreadable. Steps:
  1. Generate a key once: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  2. Add it as `FERNET_KEY` in Railway → your service → Variables
  3. Redeploy. Stored keys will survive all future redeploys.
- **Set `ALLOWED_ORIGINS` on Railway** — Should be `https://chat-merge-app-production.up.railway.app`. Without it the default `["*"]` allows any origin (CORS).
- **Fix Railway auto-deploy** — GitHub App permissions broke during setup. Fix:
  1. github.com → Settings → Applications → Railway → Configure
  2. Add `qsimeon/chat-merge-app` to the allowed repositories list
  3. Back in Railway → your service → Settings → Source → reconnect
- **Persistent file uploads** — Mount a Railway volume at `/app/backend/uploads` (service → Settings → Volumes). Without it, uploaded files vanish on each redeploy. For a no-uploads demo this is fine; for real use it matters.
- **Verify production CTA** — Just pushed the "Get started in 2 steps" landing-page update. Trigger a manual Railway redeploy (until auto-deploy is fixed), then confirm it renders correctly.
- **Pinecone in production** — The Pinecone index must be manually created or exist before a user adds a Pinecone API key. The app creates it lazily on first use, which may timeout on cold start. Consider pre-creating index `chatmerge` (dimension 1536, cosine, us-east-1) or documenting this for users.

### Claude Can Handle
- **`backend/requirements.txt` redundancy** — Duplicates `pyproject.toml`. Only kept for `start.sh`'s `pip install` fallback path (when uv isn't present). Safe to delete if `start.sh` is updated to require uv (which is already the default for dev and Dockerfile).
- **VectorStore abstraction** — Extract a `VectorStore` ABC from `vector_service.py`; add `PineconeVectorStore` implementation. Makes swapping to Qdrant/Weaviate/Chroma trivial.

## Cleanup Recommendations

### Safe to Delete (with confirmation)
- `backend/requirements.txt` — Exact duplicate of `pyproject.toml` deps. `start.sh` uses it only as a fallback when uv isn't present. If `start.sh`'s pip branch is removed (or left as-is), this file is maintenance overhead.

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

1. **Set `FERNET_KEY` on Railway** (human, urgent) — generate key once, paste into Railway Variables; prevents stored-key wipeout on redeploy
2. **Set `ALLOWED_ORIGINS` on Railway** (human) — lock CORS to your Railway domain
3. **Fix Railway auto-deploy** (human) — 5-minute GitHub App permissions fix unlocks push-to-deploy
4. **Persistent file uploads** (human) — mount Railway volume at `/app/backend/uploads` for production durability
