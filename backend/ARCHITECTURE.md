# Architecture Documentation

## System Overview

ChatMerge is a modular, async-first FastAPI backend that orchestrates multi-provider AI chat, vector-fusion conversation merging, RAG-powered context retrieval, and file attachment handling.

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│                      (main.py)                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
    ┌─────────┐        ┌─────────┐       ┌──────────┐
    │  Routes │        │Services │       │Providers │
    │         │        │         │       │          │
    │ /chats  │        │Completion│      │ OpenAI   │
    │ /msgs   │        │Merge    │       │Anthropic │
    │ /attach │        │Vector   │       │ Gemini   │
    │ /keys   │        │Storage  │       │          │
    │ /merge  │        │Encrypt  │       └────┬─────┘
    └────┬────┘        └────┬────┘            │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │                            │
              ▼                            ▼
      ┌──────────────┐             ┌──────────────┐
      │   Database   │             │   Pinecone   │
      │   (SQLite /  │             │  Vector Store│
      │  PostgreSQL) │             │  (per-chat   │
      │              │             │  namespaces) │
      │ Chat         │             └──────────────┘
      │ Message      │
      │ Attachment   │
      │ APIKey       │
      │ MergeHistory │
      └──────────────┘
```

## Module Breakdown

### Entry Point: main.py

Creates and configures the FastAPI app:
- Initializes CORS middleware
- Registers all routers
- Mounts static files (for frontend dist)
- Runs startup: creates DB tables, runs `is_merged` column migration
- Health check endpoint at `/health` (includes `rag_enabled` flag)

### Database Layer: app/database.py

- `SQLAlchemy AsyncEngine` with `aiosqlite` (dev) or `asyncpg` (prod)
- `async_sessionmaker` factory for sessions
- `Base` declarative base for ORM models
- `create_tables()` + `migrate_add_is_merged()` on startup

**Session pattern:**
```python
async with async_session() as session:
    await session.commit()
```

### Models: app/models.py

#### Chat
- `id`, `title`, `provider`, `model`, `system_prompt`
- `is_merged` (Boolean, default False) — drives always-RAG path in completion_service
- `created_at`, `updated_at`

#### Message
- `id`, `chat_id` (FK cascade), `role`, `content`, `created_at`
- One-to-many with `Attachment` (`lazy="selectin"`)

#### Attachment
- `id`, `message_id` (FK cascade), `file_name`, `file_type`, `file_size`
- `storage_path` — local path or Vercel Blob URL

#### APIKey
- `id`, `provider` (unique), `encrypted_key`, `is_active`

#### MergeHistory
- `id`, `source_chat_ids` (JSON), `merged_chat_id` (FK), `merge_model`

### Services: app/services/

#### completion_service.py — Streaming + RAG

**`stream_chat_completion()`**:
1. Load chat; detect `chat.is_merged`
2. For **merged chats**: call `_build_merged_chat_context()` — embeds user query, queries fused Pinecone namespace, injects top-K context block into system prompt
3. For **regular chats**: standard message history build; RAG fallback if history > threshold
4. Strip any leading non-user messages (Gemini/Anthropic require user-first conversations)
5. Stream from provider, accumulate, save assistant message + trigger vector storage

#### merge_service.py — Vector-Fusion Merge

**`merge_chats()`** — zero message copying:
1. Load source chats + sample messages for AI intro generation
2. Create empty merged chat with `is_merged=True`
3. Call `vector_service.fuse_namespaces()` — the core fusion
4. Generate AI intro message ("I've merged [A] and [B]...")
5. Save intro as first (only) assistant message
6. Record `MergeHistory`
7. Yield `merge_complete` event

#### vector_service.py — Pinecone RAG

**`store_message_vector()`**: Embeds message content with `text-embedding-3-small`, upserts to chat's Pinecone namespace. Fire-and-forget via `asyncio.create_task()`.

**`fuse_namespaces(source_ids, target_id, ...)`**: The innovation —
```
working_set = all vectors from source A
for each vector w in source B:
    nn = nearest neighbor in working_set (cosine similarity via numpy)
    if cosine(w, nn) >= 0.82:
        replace nn with normalize((nn + w) / 2)   # averaged embedding
    else:
        append w                                   # unique concept, keep both
upsert working_set → target namespace
```
Result size: between `max(|A|,|B|)` and `|A|+|B|`. Semantically redundant content is compressed; unique concepts are preserved.

**`query_relevant_context()`**: Embeds query, fetches top-K matches from namespace, returns content strings.

#### storage_service.py — File Storage

Abstracts local filesystem vs Vercel Blob:
- Local: saves to `backend/uploads/{uuid}`
- Vercel Blob: uploads via REST API using `BLOB_READ_WRITE_TOKEN`
- `get_file(path)` returns bytes regardless of backend

#### encryption_service.py — API Key Security

Fernet symmetric encryption. Key stored in `.encryption_key` (gitignored).
- `encrypt_key(plain)` → encrypted string stored in DB
- `decrypt_key(encrypted)` → plaintext for provider calls

### Providers: app/providers/

#### BaseProvider (base.py)
```python
async def stream_completion(
    messages: List[dict],      # {role, content, attachments?}
    model: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
) -> AsyncGenerator[StreamChunk, None]
```

`StreamChunk.type`: `content | error | done | warning | merge_complete`

#### OpenAIProvider
- Images: base64 `image_url` content blocks
- o-series: no `temperature`, `developer` role, `max_completion_tokens`

#### AnthropicProvider
- Images: base64 `image` content blocks
- Extended thinking: `temperature=1` required when enabled

#### GeminiProvider
- Uses `google-genai` SDK (`genai.Client`), NOT `google-generativeai`
- Images: `types.Part.from_bytes()`
- Role mapping: `"assistant"` → `"model"`

### Routes: app/routes/

| File | Endpoints |
|------|-----------|
| `chats.py` | `GET/POST /api/chats`, `GET/PATCH/DELETE /api/chats/{id}` |
| `messages.py` | `GET /api/chats/{id}/messages`, `POST /api/chats/{id}/completions` (SSE) |
| `attachments.py` | `POST /api/attachments`, `GET /api/attachments/{id}`, `DELETE /api/attachments/{id}` |
| `api_keys.py` | `GET/POST /api/api-keys`, `DELETE /api/api-keys/{id}` |
| `merge.py` | `POST /api/merge` (SSE), `GET /api/models` |

## Data Flow: Vector-Fusion Merge

```
POST /api/merge {chat_ids: [A, B], merge_provider, merge_model}
  │
  ├─ merge_service.merge_chats()
  │   ├─ Create empty merged Chat (is_merged=True)
  │   ├─ vector_service.fuse_namespaces(A, B → merged_chat_id)
  │   │   ├─ fetch all vectors from namespace A
  │   │   ├─ fetch all vectors from namespace B
  │   │   ├─ nearest-neighbor fusion loop (numpy cosine)
  │   │   └─ upsert fused set → merged_chat namespace
  │   ├─ Generate AI intro via provider.stream_completion()
  │   ├─ Save intro as message
  │   └─ yield merge_complete {merged_chat_id}
  │
Client navigates to merged chat
```

## Data Flow: Merged Chat Completion

```
POST /api/chats/{merged_id}/completions {content: "Who am I?"}
  │
  ├─ completion_service (detects is_merged=True)
  │   ├─ _build_merged_chat_context()
  │   │   ├─ embed "Who am I?" → vector
  │   │   ├─ query merged namespace top-8
  │   │   └─ build context block string
  │   ├─ system_prompt += context block
  │   ├─ strip leading non-user messages
  │   ├─ provider.stream_completion(messages, system_prompt)
  │   └─ yield chunks → SSE to client
```

## Security

1. **API Keys**: Encrypted at rest via Fernet; never logged or returned in API responses
2. **CORS**: Permissive in dev (`*`); set `ALLOWED_ORIGINS` in production
3. **SQL Injection**: Protected by SQLAlchemy ORM parameterized queries
4. **Validation**: Pydantic schemas validate all request inputs
5. **File uploads**: Stored with UUID filenames; served only via authenticated endpoint

## Performance

- **Streaming**: Responses chunked directly to client via SSE; no buffering
- **Async I/O**: All DB and provider calls are non-blocking
- **Vector ops**: Fire-and-forget via `asyncio.create_task()` — never blocks message save
- **RAG**: Only top-K chunks injected; scales to arbitrarily long source conversations
