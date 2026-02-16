# Architecture Documentation

## System Overview

The Chat Merge App backend is a modular, async-first FastAPI application that orchestrates interactions with multiple AI providers and intelligently merges conversations.

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
    │  Routes │        │ Services│       │ Providers│
    │         │        │         │       │          │
    │ /chats  │        │ Chat    │       │ OpenAI   │
    │ /msgs   │        │ Merge   │       │ Anthropic│
    │ /keys   │        │ Encrypt │       │ Gemini   │
    │ /merge  │        │         │       │          │
    └────┬────┘        └────┬────┘       └────┬─────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
            ┌─────────────┐       ┌──────────┐
            │   Database  │       │Encryption│
            │             │       │ (Fernet) │
            │ Chat        │       └──────────┘
            │ Message     │
            │ APIKey      │
            │ MergeHist   │
            └─────────────┘
```

## Module Breakdown

### Entry Point: main.py

Creates and configures the FastAPI app:
- Initializes CORS middleware
- Registers all routers
- Mounts static files (for frontend)
- Sets up startup event to create database tables
- Provides health check endpoint

**Key functions:**
- `startup_event()`: Async initialization
- `root()`: Serves frontend index.html
- `health_check()`: Returns {"status": "ok"}

### Database Layer: app/database.py

Manages SQLAlchemy async configuration:
- `SQLAlchemy AsyncEngine` with aiosqlite
- `async_sessionmaker` factory for sessions
- `Base` declarative base for ORM models
- `create_tables()` async function to initialize schema

**Pattern:**
```python
async with async_session() as session:
    # Use session
    await session.commit()
```

### Models: app/models.py

Four SQLAlchemy ORM models:

#### Chat
- Represents a conversation session
- Links to multiple Messages
- Stores provider, model, system prompt
- Timestamps for tracking

#### Message
- Individual message in a chat
- Tracks role (user/assistant/system)
- Stores reasoning trace for extended thinking
- Foreign key to Chat (with cascade delete)

#### APIKey
- Encrypted provider API keys
- Active flag for enable/disable
- Unique per provider

#### MergeHistory
- Tracks merge operations
- Stores source chat IDs and merged chat ID
- Records which model was used for merge

### Schemas: app/schemas.py

Pydantic models for validation and API documentation:

**Request schemas:**
- `ChatCreate`: Title, provider, model, system_prompt
- `CompletionRequest`: Content, temperature, max_tokens
- `APIKeyCreate`: Provider, api_key
- `MergeRequest`: chat_ids, merge_provider, merge_model

**Response schemas:**
- `MessageResponse`: Full message with metadata
- `ChatResponse`: Chat with all messages
- `ChatListItem`: Compact chat info for lists
- `APIKeyResponse`: Safe API key info (no secret)
- `ModelsResponse`: Available models per provider

### Providers: app/providers/

Abstract provider pattern with three implementations.

#### BaseProvider (base.py)
Abstract class defining provider interface:
```python
async def stream_completion(
    messages: List[dict],
    model: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[StreamChunk, None]
```

Yields `StreamChunk` objects with type and data.

#### OpenAIProvider (openai_provider.py)
- Uses `AsyncOpenAI` client
- Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, o1, o1-mini
- Adds system_prompt as first message
- Streams with `stream=True`

#### AnthropicProvider (anthropic_provider.py)
- Uses `AsyncAnthropic` client
- Models: claude-sonnet-4-20250514, claude-haiku-4-20250414, claude-opus-4-20250514
- System prompt passed via `system` parameter
- Distinguishes thinking blocks (reasoning) from text blocks
- Yields both content and reasoning chunks

#### GeminiProvider (gemini_provider.py)
- Uses `genai.GenerativeModel` (synchronous API wrapped async)
- Models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
- Converts standard message format to Gemini format
- Role mapping: "assistant" → "model"
- Content structure: `{"parts": [{"text": "..."}]}`

#### Factory (factory.py)
```python
def create_provider(provider_name: str, api_key: str) -> BaseProvider
def get_all_models() -> Dict[str, List[str]]
```

Centralizes provider instantiation and model enumeration.

### Services: app/services/

Business logic layer with async operations.

#### chat_service.py
CRUD operations on Chat and Message entities:
- `create_chat(db, chat_data)`: Insert new chat
- `get_chats(db)`: List all chats with counts
- `get_chat(db, chat_id)`: Fetch one chat with messages
- `update_chat(db, chat_id, updates)`: Modify title/system_prompt
- `delete_chat(db, chat_id)`: Remove chat and cascade messages
- `get_messages(db, chat_id)`: Get messages for a chat
- `create_message(db, chat_id, role, content, reasoning)`: Add message

All functions are async and properly handle database sessions.

#### completion_service.py
Streaming chat completions with database persistence:

**`stream_chat_completion(db, chat_id, user_content, ...)`**
1. Load chat and verify it exists
2. Retrieve all previous messages
3. Append user message to history
4. Save user message to database
5. Get decrypted API key for chat's provider
6. Create provider instance via factory
7. Stream completion from provider
8. Accumulate content and reasoning
9. On completion, save assistant message to database
10. Yield chunks to caller

Handles errors gracefully with error chunks.

#### merge_service.py
Intelligent conversation merging (the core feature).

**Key components:**

`MERGE_SYSTEM_PROMPT`: Detailed instructions for synthesis algorithm

`_format_conversation()`: Format chat + messages into structured text:
```
## Conversation: "Title"
Provider: X / Model: Y

USER: message
ASSISTANT: response
[REASONING]: thinking
```

`_parse_merged_response()`: Parse merge output using strict format:
```
[USER]: content
[ASSISTANT]: content
[REASONING]: optional
```

**`merge_chats(db, chat_ids, merge_provider, merge_model)`**:
1. Load all specified chats
2. Format each as structured text
3. Combine into one merge prompt
4. Stream from merge model
5. Parse output into (role, content, reasoning) tuples
6. Create new Chat with merged title
7. Save all parsed messages
8. Create MergeHistory record
9. Yield merge_complete event with merged chat ID

#### encryption_service.py
Symmetric encryption using Fernet (industry standard):

- `_get_or_create_encryption_key()`: Loads from or generates `.encryption_key`
- `encrypt_key(plain_key)`: Returns base64-encoded ciphertext
- `decrypt_key(encrypted_key)`: Returns decrypted plaintext

**Security note:** The `.encryption_key` file must be:
- Not committed to version control
- Protected with proper file permissions (chmod 600)
- Backed up securely if persistence is needed
- Never transmitted over network

### Routes: app/routes/

FastAPI routers organized by resource.

#### chats.py
REST endpoints for chat management:
- `POST /api/chats/`: Create
- `GET /api/chats/`: List
- `GET /api/chats/{id}`: Read
- `PATCH /api/chats/{id}`: Update
- `DELETE /api/chats/{id}`: Delete

All endpoints:
- Get session via dependency injection
- Return proper HTTP status codes
- Log errors
- Return appropriate response schemas

#### messages.py
Message retrieval and streaming completions:
- `GET /api/chats/{id}/messages`: List messages
- `POST /api/chats/{id}/completions`: Stream completion (SSE)

**SSE Implementation:**
- Uses `sse_starlette.EventSourceResponse`
- Wraps `stream_chat_completion()` generator
- Each event is JSON: `{"type": "...", "data": "..."}`
- Client can handle streaming with EventSource API

#### api_keys.py
API key lifecycle management:
- `POST /api/api-keys/`: Store (with encryption)
- `GET /api/api-keys/`: List (safe, no secrets)
- `DELETE /api/api-keys/{id}`: Remove
- `POST /api/api-keys/validate`: Test key validity

**Key features:**
- Update-or-insert logic (idempotent)
- Never returns decrypted keys
- Validates with provider before storing (optional)

#### merge.py
Merge operations and model discovery:
- `POST /api/merge`: Merge chats (SSE streaming)
- `GET /api/models`: List all available models

**Merge response:**
- Streams events during processing
- Final event type is `merge_complete` with merged chat ID
- Client awaits this event to get result

## Data Flow Examples

### Chat Completion Flow

```
1. User POST /api/chats/{id}/completions
   └─ Request: {"content": "Hello"}

2. Route receives request
   ├─ Get chat from database
   ├─ Call completion_service.stream_chat_completion()
   │
   └─ completion_service:
      ├─ Load all previous messages
      ├─ Save user message
      ├─ Get decrypted API key
      ├─ Create provider
      │
      └─ provider.stream_completion():
         ├─ Call API
         ├─ Yield StreamChunk objects
         │
      ├─ Accumulate response
      ├─ Save assistant message
      └─ Yield chunks to client

3. Route wraps in EventSourceResponse
   └─ Each chunk becomes SSE event

4. Client receives events:
   {"type": "content", "data": "Hello..."}
   {"type": "content", "data": " there!"}
   {"type": "done", "data": ""}
```

### Merge Flow

```
1. User POST /api/merge
   └─ Request: {chat_ids: [...], merge_provider: "...", merge_model: "..."}

2. Route calls merge_service.merge_chats()

3. merge_service:
   ├─ Load all chats and their messages
   ├─ Format as text
   ├─ Build merge prompt with system instructions
   ├─ Create merge provider
   │
   ├─ provider.stream_completion(merge_prompt):
   │  ├─ API call
   │  ├─ Stream response
   │
   ├─ Accumulate full response
   ├─ Parse [USER]/[ASSISTANT] format
   ├─ Create new Chat
   ├─ Save parsed messages
   ├─ Create MergeHistory record
   └─ Yield merge_complete event

4. Client receives final event:
   {"type": "merge_complete", "data": "merged-chat-id"}
```

## Error Handling Strategy

All async functions implement layered error handling:

1. **Provider Layer**: Yields error chunks if API call fails
2. **Service Layer**: Catches provider errors, logs, yields error chunks
3. **Route Layer**: Catches service errors, returns HTTP error response
4. **Top Level**: CORS and unhandled exceptions return 500

Error response format:
```json
{
  "detail": "Human-readable error message"
}
```

## Async/Await Patterns

All database operations use async context managers:
```python
async with async_session() as db:
    result = await db.execute(select(...))
    rows = result.scalars().all()
    await db.commit()
```

All provider operations are async generators:
```python
async for chunk in provider.stream_completion(...):
    # Handle chunk
```

All routes use `async def` with async service calls.

## Performance Considerations

1. **Streaming**: Large responses don't require buffering - streamed directly to client
2. **Async I/O**: Non-blocking database and API calls via asyncio
3. **Connection Pooling**: SQLAlchemy maintains connection pool
4. **Message Ordering**: Database ORDERED BY created_at ensures consistency
5. **Lazy Loading**: Messages loaded only when needed via relationships

## Security Considerations

1. **API Keys**: Encrypted at rest using Fernet
2. **CORS**: Currently permissive (for development)
3. **SQL Injection**: Protected by SQLAlchemy ORM
4. **Validation**: Pydantic schemas validate all inputs
5. **No Logging of Secrets**: API keys never logged
6. **Encryption Key**: Must be protected in production

## Future Extensions

1. **Authentication**: Add user authentication and isolation
2. **Caching**: Redis cache for frequently accessed chats
3. **Vector Search**: Embed messages for semantic search
4. **Rate Limiting**: Per-user API quotas
5. **Webhooks**: Async notifications on completion
6. **Batch Operations**: Process multiple chats in parallel
7. **Analytics**: Track usage and model performance
8. **Custom Providers**: Plugin architecture for new AI services

## Database Schema

```sql
CREATE TABLE chats (
    id TEXT PRIMARY KEY,
    title TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    system_prompt TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT FOREIGN KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning_trace TEXT,
    created_at DATETIME
);

CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    provider TEXT UNIQUE NOT NULL,
    encrypted_key TEXT NOT NULL,
    is_active BOOLEAN,
    created_at DATETIME
);

CREATE TABLE merge_history (
    id TEXT PRIMARY KEY,
    source_chat_ids JSON,
    merged_chat_id TEXT FOREIGN KEY,
    merge_model TEXT NOT NULL,
    created_at DATETIME
);
```

All id columns use UUID strings for global uniqueness without database coordination.
