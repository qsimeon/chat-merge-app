# ChatMerge — Claude Code Session Initialization Prompt

Copy everything below this line and paste it as your first message when starting a new Claude Code session in the `~/chat-merge-app` directory.

---

## Context: What This Project Is

You are continuing development on **ChatMerge**, a multi-provider AI chat application with a unique "merge chats" feature. The app connects to OpenAI, Anthropic, and Google Gemini APIs through a single ChatGPT/Claude-like dark-themed interface. Its core feature is vector-fusion merging: when you merge two conversations, their Pinecone vector namespaces are intelligently fused (nearest-neighbor + averaging), and the resulting merged chat uses RAG exclusively for context — no message copying, no context-window blowup.

**The motivation**: People have great conversations spread across different AI systems but can't combine them. ChatMerge solves this by semantically fusing the vector representations of conversations, then letting you continue chatting against that fused semantic memory.

The project is feature-complete for its v1 demo. All three providers work, merging with vector fusion works, file/image uploads work, the dark-themed UI is functional, and a full Playwright test suite passes (9/9).

## Current Architecture

### Tech Stack
- **Backend**: Python FastAPI (async), SQLAlchemy ORM, SQLite via aiosqlite, Fernet encryption for API keys, uv for package management
- **Frontend**: React 18 + TypeScript + Vite + Zustand (state management) + Lucide icons
- **Vector Store**: Pinecone serverless, `text-embedding-3-small` embeddings, one namespace per chat
- **Streaming**: Server-Sent Events (SSE) via `StreamingResponse` with manual `data: {json}\n\n` formatting
- **File Storage**: Local `backend/uploads/` (dev) or Vercel Blob (prod)
- **No auth** — single-user local app

### Directory Structure
```
chat-merge-app/
├── backend/
│   ├── main.py                          # FastAPI app, CORS, static file serving, startup
│   ├── requirements.txt                 # Python deps (also pyproject.toml for uv)
│   ├── app/
│   │   ├── database.py                  # SQLAlchemy async engine, startup migration for is_merged col
│   │   ├── models.py                    # ORM: Chat (is_merged), Message, Attachment, APIKey, MergeHistory
│   │   ├── schemas.py                   # Pydantic request/response models (includes AttachmentResponse)
│   │   ├── providers/
│   │   │   ├── base.py                  # Abstract BaseProvider + StreamChunk dataclass
│   │   │   ├── factory.py               # create_provider() factory
│   │   │   ├── openai_provider.py       # OpenAI — images via base64 content blocks
│   │   │   ├── anthropic_provider.py    # Anthropic — images via base64 content blocks
│   │   │   └── gemini_provider.py       # google-genai SDK (not google-generativeai)
│   │   ├── routes/
│   │   │   ├── chats.py                 # CRUD: /api/chats (includes is_merged in responses)
│   │   │   ├── messages.py              # Streaming: /api/chats/{id}/completions; GET includes attachments
│   │   │   ├── attachments.py           # Upload/download: /api/attachments
│   │   │   ├── api_keys.py              # Key management: /api/api-keys
│   │   │   └── merge.py                 # Merge streaming: /api/merge
│   │   └── services/
│   │       ├── chat_service.py          # Chat/message CRUD operations
│   │       ├── completion_service.py    # Streaming + merged-chat RAG path + leading-msg strip
│   │       ├── merge_service.py         # Vector-fusion merge (zero message copying)
│   │       ├── vector_service.py        # Pinecone: store, query, fuse_namespaces()
│   │       ├── storage_service.py       # Local or Vercel Blob file storage
│   │       └── encryption_service.py    # Fernet encrypt/decrypt for API keys
├── frontend/
│   ├── src/
│   │   ├── api.ts                       # API layer with SSE streaming
│   │   ├── store.ts                     # Zustand store (all state + actions, handles warning chunks)
│   │   ├── types.ts                     # TypeScript interfaces; LLM_PROVIDER_LABELS (no Pinecone)
│   │   ├── index.css                    # Full dark theme CSS
│   │   └── components/
│   │       ├── App.tsx                  # Main layout
│   │       ├── Sidebar.tsx              # Chat list + merge button (uses LLM_PROVIDER_LABELS)
│   │       ├── ChatArea.tsx             # Message display + RAG-powered badge for merged chats
│   │       ├── InputArea.tsx            # Text input + file upload
│   │       ├── MessageBubble.tsx        # Message render + attachment display
│   │       ├── MergeModal.tsx           # Merge UI — green banner when RAG enabled; uses LLM_PROVIDER_LABELS
│   │       └── SettingsModal.tsx        # API key management (all 4 providers including Pinecone)
├── tests/
│   └── playwright_full_test.py          # 9-test Playwright suite (9/9 passing)
├── start.sh                             # Startup script
├── vercel.json                          # Vercel deployment config
└── api/index.py                         # Vercel Python entry point
```

### Database Schema
- **Chat**: id (UUID), title, provider, model, system_prompt, `is_merged` (bool), created_at, updated_at
- **Message**: id (UUID), chat_id (FK), role (user/assistant/system), content, created_at
- **Attachment**: id (UUID), message_id (FK), file_name, file_type, file_size, storage_path, created_at
- **APIKey**: id (UUID), provider (unique), encrypted_key, is_active, created_at
- **MergeHistory**: id (UUID), source_chat_ids (JSON), merged_chat_id (FK), merge_model, created_at

### Key Implementation Details

**Vector-fusion merge** (`vector_service.fuse_namespaces()`):
- Fetches all vectors from each source namespace
- For each vector in source B: if cosine similarity with nearest neighbor in A ≥ 0.82, replace that neighbor with the normalized average; otherwise append as unique
- Result is stored in the merged chat's Pinecone namespace
- `numpy` used for cosine similarity (local, no API calls)

**Merged-chat completions** (`completion_service._build_merged_chat_context()`):
- Detects `chat.is_merged == True` → always uses RAG (not the message-count threshold)
- Embeds user query → queries fused namespace (top_k=8) → injects as context block in system prompt
- Recent messages in the merged chat (post-merge) are included as normal history
- Leading non-user messages stripped before provider calls (Gemini/Anthropic require user-first conversations)

**Provider abstraction**: `BaseProvider` abstract class with `stream_completion()` returning `AsyncGenerator[StreamChunk, None]`. `StreamChunk` has `type` (content/reasoning/error/done/warning/merge_complete) and `data`.

**Attachment handling**: Images supported natively by all three providers (OpenAI: base64 image_url blocks; Anthropic: base64 image blocks; Gemini: inline_data parts). Non-image files sent as text context.

**`LLM_PROVIDER_LABELS` vs `PROVIDER_LABELS`**: `LLM_PROVIDER_LABELS` = {openai, anthropic, gemini}. `PROVIDER_LABELS` = {openai, anthropic, gemini, pinecone}. Chat creation and merge UI must use `LLM_PROVIDER_LABELS`; Settings modal uses `PROVIDER_LABELS`.

## Commands

```bash
# Backend
cd backend && uv run uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Import check
cd backend && uv run python -c "from main import app; print('OK')"

# Playwright tests (requires both servers running)
python3 tests/playwright_full_test.py
```

## Critical Invariants (Don't Break These)

1. **Streaming generators own their DB sessions** — never use `Depends(get_db)` inside a streaming generator
2. **Merged chats have zero copied messages** — all context via RAG from fused Pinecone namespace
3. **Strip leading non-user messages** before any provider API call (Gemini/Anthropic reject assistant-first history)
4. **Pinecone ops gated on `vector_service.is_configured()`** — app works without Pinecone (falls back to simple union)
5. **Anthropic extended thinking requires `temperature=1`**
6. **OpenAI o-series**: no `temperature`, use `developer` role, use `max_completion_tokens`
7. **Gemini SDK is `google-genai`** (not `google-generativeai`)

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI chat + embeddings |
| `ANTHROPIC_API_KEY` | Anthropic chat |
| `GOOGLE_API_KEY` | Gemini chat |
| `PINECONE_API_KEY` | Vector store (required for smart fusion) |
| `DATABASE_URL` | PostgreSQL URL (optional, defaults to SQLite) |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob for file storage (optional) |
| `ALLOWED_ORIGINS` | CORS (optional, defaults to `*` for dev) |
