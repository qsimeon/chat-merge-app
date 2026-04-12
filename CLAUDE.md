# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.
See **AGENTS.md** for the full project reference (architecture, commands, invariants, patterns).

## Quick Start

```bash
# Full stack (recommended)
./start.sh

# Backend only
cd backend && uv run uvicorn main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev
```

## Critical Invariants (read before changing anything)

1. Streaming generators must own their DB sessions — never use `Depends(get_db)` inside a generator.
2. Anthropic extended thinking requires `temperature=1`.
3. OpenAI o-series: no `temperature`, use `developer` role, use `max_completion_tokens`.
4. Gemini SDK is `google-genai` (NOT `google-generativeai`).
5. RAG is fire-and-forget: `asyncio.create_task(vector_service.store_message_vector(...))`.
6. Always call `vector_service.is_configured()` before any Pinecone operations.
7. Merged chats (`is_merged=True`) have zero copied messages — context comes entirely from RAG.
8. Strip leading non-user messages before provider calls (Gemini + Anthropic require `role="user"` first).
9. Use `LLM_PROVIDER_LABELS` in chat/merge UI — NOT `PROVIDER_LABELS` (which includes Pinecone).

## Key Files

| Changing... | Read first |
|-------------|------------|
| Merge behavior | `backend/app/services/merge_service.py`, `vector_service.py` |
| Streaming | `backend/app/services/completion_service.py`, `routes/messages.py` |
| Provider behavior | `backend/app/providers/base.py`, specific provider file |
| Frontend state | `frontend/src/store.ts`, `frontend/src/api.ts` |
| Model lists | `frontend/src/types.ts` AND `backend/app/providers/{provider}_provider.py` (keep in sync) |

## Environment

- **Local**: SQLite (auto), no Docker needed
- **Railway**: PostgreSQL (injected via `DATABASE_URL`), auto-deploys from GitHub push
- **API keys**: browser localStorage only, sent as request headers — never server-side env vars
- **Pinecone index**: hardcoded as `"chatmerge"` — must be created before deploying

Full details: **AGENTS.md**
