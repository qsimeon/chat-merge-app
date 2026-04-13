# RALPH.md — chat-merge-app

## Project Goal
Build a production-ready multi-provider AI chat application with smart conversation merging powered by vector-fusion RAG, deployable on Railway with zero server-side API key storage.

## Deliverable Type
Full-stack web application: FastAPI (Python 3.11) backend + React/TypeScript/Vite frontend, containerized via Docker, deployed on Railway.

## Audience
AI power users and researchers who actively work with multiple LLM providers (OpenAI, Anthropic, Google Gemini) and want to compare model responses, merge conversation threads, and synthesize knowledge across providers using RAG.

## Success Criteria
1. **All providers stream reliably** — OpenAI (including o-series), Anthropic (including extended thinking), Gemini (including thinking models) all return correct streaming completions
2. **Merge works correctly** — Vector-fusion fuse_namespaces() merges 2+ chats into a RAG-only merged chat; no hallucination when RAG returns 0 hits
3. **Test suite passes** — tests/playwright_full_test.py runs clean against local stack (frontend :5173, backend :8000)
4. **Railway deployment is healthy** — /health endpoint returns 200, Dockerfile builds successfully, PostgreSQL works
5. **Pinecone RAG enabled** — embeddings store on message send (fire-and-forget), retrieve on completion, gracefully degrade when Pinecone key absent
6. **No regressions** — All previously fixed bugs stay fixed (Gemini embeddings, o-series temperature, truncated Gemini thinking intros)

## Design Philosophy
- **Browser-side keys only** — API keys live in localStorage, sent as request headers; never persisted server-side
- **Streaming-first** — all LLM completions use SSE; merge also streams progress events
- **RAG as enhancement** — regular chats optionally use Pinecone; merged chats use RAG exclusively (no message copying)
- **Minimal infrastructure** — SQLite locally, PostgreSQL on Railway, no Redis/Celery/Docker Compose needed locally
- **Provider parity** — each provider follows its own quirks (Gemini: google-genai SDK; o-series: no temperature; Anthropic thinking: temperature=1)

## Constraints (NEVER violate)
1. Streaming generators own their own DB sessions — never `Depends(get_db)` inside a generator
2. Anthropic extended thinking: `temperature=1` (required by API)
3. OpenAI o-series: no `temperature` param; use `developer` role; use `max_completion_tokens`
4. Gemini SDK: `google-genai` only (NOT `google-generativeai`)
5. RAG calls: always fire-and-forget via `asyncio.create_task(...)`
6. Always call `vector_service.is_configured()` before any Pinecone operation
7. Merged chats (`is_merged=True`): zero copied messages — context via RAG only
8. Strip leading non-user messages before provider calls (Gemini + Anthropic require user-first)
9. Use `LLM_PROVIDER_LABELS` (not `PROVIDER_LABELS`) in chat/merge UI
10. Pinecone index name is hardcoded as `"chatmerge"` — must be pre-created before deploying

## Current State: ~95%

### What Works
- Multi-provider streaming (OpenAI GPT-4o/o-series, Anthropic Claude 3.x/extended thinking, Gemini 2.5 Flash/Pro/thinking)
- Chat CRUD (create, list, select, delete, rename)
- Conversation merge via vector-fusion (fuse_namespaces)
- Pinecone RAG (store on send, retrieve on completion, graceful degradation without keys)
- File/image attachment upload and multimodal messaging
- Browser-side API key management (localStorage, Settings modal)
- Railway deployment (Dockerfile, railway.toml, PostgreSQL support)
- Gemini embeddings via gemini-embedding-001 (REST bypass, 768-dim)
- Hallucination prevention when RAG returns 0 hits on merged chats
- Model list synced between frontend (types.ts) and backend (provider files)

### Known Gaps / Next Work
- **Tests**: Only one Playwright e2e test file (tests/playwright_full_test.py); no backend unit tests; no playwright.config.ts; test file may be stale
- **Playwright config**: No playwright.config.ts — tests require manual server setup
- **Backend unit tests**: Zero coverage for services (completion, merge, vector, chat)
- **Frontend tests**: No component/unit tests
- **Dependency freshness**: Some packages may be behind latest (lucide-react, zustand, fastapi)
- **Error UX**: Some error states may not surface clearly in the UI
- **Docs**: AGENTS.md model lists need periodic refresh as providers release new models

## Human Actions Needed
1. **Pinecone setup**: Create an index named `"chatmerge"` with 768 dimensions (cosine similarity) in your Pinecone account before deploying or enabling RAG
2. **Railway setup**: Connect GitHub repo to Railway project; set no env vars (API keys are browser-side); ensure persistent volume for SQLite if not using PostgreSQL
3. **Browser API keys**: After opening the app, go to Settings and enter API keys for the providers you want to use
4. **Domain/SSL**: Configure Railway custom domain if desired (uvicorn runs with `--proxy-headers` for HTTPS termination)

## Codex Delegation Guide

### Delegate to `/codex:rescue`
- Implementing new features (e.g., chat export, message editing, new provider support)
- Writing Playwright e2e tests or backend pytest tests
- Adding playwright.config.ts and test infrastructure
- Fixing streaming bugs or provider-specific issues
- Dependency upgrades with code changes needed
- Adding new routes or service methods
- Frontend component work (new UI features, styling)

### Handle Directly (no Codex needed)
- Architecture decisions and design documents
- Reviewing code and identifying issues
- Updating AGENTS.md / README.md / CLAUDE.md with new info
- Planning the next iteration
- Reading and understanding existing code
- Git operations (commit, push, PR creation)
- Assessing test results and diagnosing failures

### Key Files to Give Codex for Context
When delegating, always include:
- `AGENTS.md` — full architecture reference and invariants
- `backend/app/services/completion_service.py` — streaming + RAG core
- `backend/app/services/merge_service.py` — merge logic
- `backend/app/providers/` — provider implementations
- `frontend/src/store.ts` — state management
- `frontend/src/types.ts` — type definitions and model lists

## Iteration Log
| Date | Goal | Outcome |
|------|------|---------|
| 2026-04-13 | First run: create RALPH.md | ✅ RALPH.md created |
