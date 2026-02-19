# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Cursor, Copilot, etc.) working in this repository.

## Project Overview

**ChatMerge** is a multi-provider AI chat application with a unique conversation merging feature. Users chat with OpenAI, Anthropic, and Google Gemini through one interface, then merge any conversations into a unified thread where the AI has full context from all source chats.

## Architecture

### Backend (Python/FastAPI)
- **Entry**: `backend/main.py` — FastAPI app, CORS, startup hooks
- **Routes**: `backend/app/routes/` — one file per resource (chats, messages, attachments, api_keys, merge)
- **Services**: `backend/app/services/` — business logic layer
- **Providers**: `backend/app/providers/` — one file per AI provider
- **Models**: `backend/app/models.py` — SQLAlchemy ORM models

### Frontend (React/TypeScript)
- **Entry**: `frontend/src/main.tsx`
- **State**: `frontend/src/store.ts` — Zustand store, ALL app state here
- **API**: `frontend/src/api.ts` — all backend calls go through this module
- **Types**: `frontend/src/types.ts` — TypeScript interfaces

### Critical Invariants

1. **Streaming sessions own their DB connections**: Streaming generators (`stream_chat_completion`, `stream_merge`) create their OWN `async with async_session()` — never use `Depends(get_db)` inside a streaming generator. FastAPI closes dependency sessions before the generator runs.

2. **Anthropic extended thinking requires `temperature=1`**: When `thinking={"type": "enabled", ...}` is set, temperature MUST be 1. Any other value causes an API error.

3. **OpenAI o-series models have restrictions**: No `temperature` parameter, use `developer` role instead of `system`, use `max_completion_tokens` instead of `max_tokens`, reasoning must use `{"effort": "high", "summary": "auto"}`.

4. **Gemini SDK is `google-genai`**: NOT `google-generativeai` (deprecated). Import as `from google import genai` and use `genai.Client(api_key=...)`.

5. **Vector storage is fire-and-forget**: `asyncio.create_task(vector_service.store_message_vector(...))` — failures are logged but never block message creation.

6. **RAG check before Pinecone ops**: Call `vector_service.is_configured()` before any Pinecone operations. App works without Pinecone (falls back to simple union merge).

7. **Merged chats have `is_merged=True` and zero copied messages**: Context comes entirely from the fused Pinecone namespace via RAG. Never copy source messages into a merged chat.

8. **Strip leading non-user messages before provider calls**: Both Gemini and Anthropic require the first message in history to be `role="user"`. The merged chat intro message is `role="assistant"`, so `completion_service` strips leading non-user messages before calling any provider.

9. **`LLM_PROVIDER_LABELS` for chat/merge UI**: Use `LLM_PROVIDER_LABELS` (openai/anthropic/gemini only), not `PROVIDER_LABELS` (which includes `pinecone`). Pinecone is a vector store, not a chat provider.

## Commands

### Running Locally
```bash
# Full stack (recommended)
./start.sh

# Backend only (with hot reload)
cd backend
uv run uvicorn main:app --reload --port 8000

# Frontend only (with hot reload, proxies API to :8000)
cd frontend
npm run dev
```

### Building
```bash
cd frontend && npm run build
```

### Testing Backend Imports
```bash
cd backend && uv run python -c "from main import app; print('OK')"
```

### Running Playwright Tests
```bash
# Requires frontend at :5173 and backend at :8000
python3 tests/playwright_full_test.py
```

## Adding a New Provider

1. Create `backend/app/providers/{name}_provider.py`:
   - Extend `BaseProvider`
   - Implement `stream_completion()` — yield `StreamChunk` objects
   - Implement `get_available_models_static()` — return list of model names
   - Handle attachments: `msg.get("attachments")` contains `[{file_type, data (base64), file_name}]`

2. Register in `backend/app/providers/factory.py`

3. Add models to `frontend/src/types.ts` in `PROVIDER_MODELS` and `LLM_PROVIDER_LABELS` (NOT `PROVIDER_LABELS` — that one includes Pinecone and is only for the Settings modal)

## Database Schema

```
Chat: id, title, provider, model, system_prompt, is_merged, created_at, updated_at
  └── Message: id, chat_id, role, content, created_at
        └── Attachment: id, message_id, file_name, file_type, file_size, storage_path, created_at
APIKey: id, provider (unique), encrypted_key, is_active
MergeHistory: id, source_chat_ids (JSON), merged_chat_id, merge_model
```

- `Chat.is_merged` — set `True` for merged chats; drives always-RAG context path in completion_service
- `Message.reasoning_trace` column was removed from the active schema
- `Attachment.storage_path` points to `backend/uploads/{uuid}` locally, or a Vercel Blob URL in production

Never store API keys in plaintext — always use `encryption_service.encrypt_key()` before saving.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | One of these required | OpenAI API key |
| `ANTHROPIC_API_KEY` | One of these required | Anthropic API key |
| `GOOGLE_API_KEY` | One of these required | Google Gemini API key |
| `PINECONE_API_KEY` | Optional | Enables RAG vector retrieval |
| `DATABASE_URL` | Optional | PostgreSQL URL (defaults to SQLite) |
| `BLOB_READ_WRITE_TOKEN` | Optional | Vercel Blob for file storage |
| `ALLOWED_ORIGINS` | Optional | CORS origins (defaults to `*` for dev) |

## Common Patterns

### Adding a new route
```python
# In backend/app/routes/myroute.py
router = APIRouter(prefix="/api", tags=["my-resource"])

async def get_db():
    async with async_session() as session:
        yield session

@router.get("/my-resource")
async def get_resource(db: AsyncSession = Depends(get_db)):
    ...
```

Then register in `backend/main.py`:
```python
from app.routes import myroute
app.include_router(myroute.router)
```

### Streaming endpoint
```python
@router.post("/my-stream")
async def my_stream(request: MyRequest):
    async def generator():
        async with async_session() as db:  # Own session!
            async for chunk in my_service(db, ...):
                yield f"data: {json.dumps({'type': chunk.type, 'data': chunk.data})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
```

### Adding state to the Zustand store
```typescript
// In frontend/src/store.ts
// 1. Add to AppState interface
myNewField: string;
myAction: () => void;

// 2. Add initial value
myNewField: '',

// 3. Implement action
myAction: () => {
  set({ myNewField: 'updated' });
},
```

## Key Files to Read Before Modifying

| If you're changing... | Read these files first |
|----------------------|------------------------|
| Merge behavior | `backend/app/services/merge_service.py`, `backend/app/services/vector_service.py` |
| Streaming/completions | `backend/app/services/completion_service.py`, `backend/app/routes/messages.py` |
| Provider behavior | `backend/app/providers/base.py`, the specific provider file |
| File uploads | `backend/app/routes/attachments.py`, `backend/app/services/storage_service.py` |
| Frontend state | `frontend/src/store.ts`, `frontend/src/api.ts` |
| Database schema | `backend/app/models.py`, `backend/app/database.py` |
| Provider dropdowns (UI) | `frontend/src/types.ts` — use `LLM_PROVIDER_LABELS`, not `PROVIDER_LABELS` |

## Deployment Notes

- Vercel Python serverless is stateless — no persistent filesystem (use Vercel Blob)
- SQLite works locally but not on Vercel — use PostgreSQL via `DATABASE_URL`
- `asyncio.create_task()` works in FastAPI async context but tasks may not complete if the function returns before them — this is acceptable for vector storage
- SSE streaming works on Vercel Pro (max 60s), may timeout on hobby tier for long completions
- Pinecone index name is hardcoded as `"chatmerge"` in `vector_service.py` — create this index before deploying
