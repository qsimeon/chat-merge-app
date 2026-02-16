# Chat Merge App - Backend

A production-ready FastAPI backend for a multi-provider AI chat application with intelligent conversation merging.

## Features

- **Multi-Provider Support**: OpenAI, Anthropic (Claude), and Google Gemini
- **Streaming Responses**: Real-time chat completions via Server-Sent Events (SSE)
- **Intelligent Merge**: Synthesize multiple conversations into one coherent dialogue
- **Secure API Key Storage**: Encrypted storage with Fernet encryption
- **Async Database**: SQLite with async SQLAlchemy
- **Reasoning/CoT Support**: Preserve extended thinking and reasoning traces from Claude
- **RESTful API**: Clean, documented endpoints

## Architecture

```
backend/
├── main.py                 # FastAPI app entry point
├── requirements.txt        # Python dependencies
├── app/
│   ├── __init__.py
│   ├── database.py         # SQLAlchemy async engine and session
│   ├── models.py           # ORM models (Chat, Message, APIKey, MergeHistory)
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── providers/          # AI provider implementations
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract BaseProvider
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── gemini_provider.py
│   │   └── factory.py      # Provider factory pattern
│   ├── services/           # Business logic services
│   │   ├── __init__.py
│   │   ├── chat_service.py        # Chat CRUD operations
│   │   ├── completion_service.py  # Streaming completions
│   │   ├── merge_service.py       # Intelligent conversation merge
│   │   └── encryption_service.py  # Fernet key management
│   └── routes/             # FastAPI routers
│       ├── __init__.py
│       ├── chats.py        # Chat endpoints
│       ├── messages.py     # Message and completion endpoints
│       ├── api_keys.py     # API key management
│       └── merge.py        # Merge and models endpoints
```

## Setup

### Prerequisites

- Python 3.8+
- pip or conda

### Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API keys:
```bash
cp .env.example .env
# Edit .env with your actual API keys
```

4. Run the server:
```bash
python main.py
```

The server will start at `http://localhost:8000`

## API Endpoints

### Chat Management

- **POST** `/api/chats/` - Create a new chat
- **GET** `/api/chats/` - List all chats
- **GET** `/api/chats/{chat_id}` - Get chat with messages
- **PATCH** `/api/chats/{chat_id}` - Update chat title/system prompt
- **DELETE** `/api/chats/{chat_id}` - Delete a chat

### Messages & Completions

- **GET** `/api/chats/{chat_id}/messages` - Get chat messages
- **POST** `/api/chats/{chat_id}/completions` - Stream chat completion (SSE)

### API Key Management

- **POST** `/api/api-keys/` - Store/update API key
- **GET** `/api/api-keys/` - List stored keys (safe - no secrets returned)
- **DELETE** `/api/api-keys/{key_id}` - Delete API key
- **POST** `/api/api-keys/validate` - Validate API key with provider

### Merge Operations

- **POST** `/api/merge` - Merge multiple chats (SSE streaming)
- **GET** `/api/models` - Get available models per provider

## Usage Examples

### Create a Chat

```bash
curl -X POST http://localhost:8000/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Python Questions",
    "provider": "openai",
    "model": "gpt-4o",
    "system_prompt": "You are a Python expert."
  }'
```

### Stream a Completion

```bash
curl -N http://localhost:8000/api/chats/{chat_id}/completions \
  -H "Content-Type: application/json" \
  -d '{"content": "How do I use async/await?"}'
```

This returns a stream of JSON events with `type` and `data` fields.

### Merge Conversations

```bash
curl -N http://localhost:8000/api/merge \
  -H "Content-Type: application/json" \
  -d '{
    "chat_ids": ["chat_id_1", "chat_id_2"],
    "merge_provider": "anthropic",
    "merge_model": "claude-opus-4-20250514"
  }'
```

Returns a stream of events. The final event with type `merge_complete` contains the merged chat ID.

## Database

SQLite database is stored in `chat_app.db` by default.

### Models

- **Chat**: Conversation with provider, model, system prompt
- **Message**: Individual messages with role, content, reasoning
- **APIKey**: Encrypted provider API keys
- **MergeHistory**: Track which chats were merged

All database operations are async-safe using SQLAlchemy's async API.

## Security

- API keys are encrypted using Fernet (symmetric encryption)
- Encryption key is stored in `.encryption_key` file (do not commit!)
- Sensitive information (keys) is never returned in API responses
- CORS is enabled for development (configure for production)

## Streaming Protocol

Both completions and merge endpoints use Server-Sent Events (SSE) for real-time streaming.

### Event Types

- **content**: Text chunk from the model
- **reasoning**: Extended thinking/CoT from Claude
- **error**: Error message
- **done**: Completion signal
- **merge_complete**: Final event for merge (contains merged chat ID)

Each event is a JSON object with `type` and `data` fields.

## Providers

### OpenAI
- Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, o1, o1-mini
- Uses AsyncOpenAI client for streaming

### Anthropic (Claude)
- Models: claude-sonnet-4-20250514, claude-haiku-4-20250414, claude-opus-4-20250514
- Supports extended thinking with reasoning extraction
- System prompt passed via `system` parameter (not as message)

### Google Gemini
- Models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
- Automatic message format conversion
- Streaming via generate_content

## Merge Algorithm

The intelligent merge algorithm:

1. Loads all conversations
2. Formats each with labels (source provider, model, etc.)
3. Sends to a designated merge model with a synthesis prompt
4. Parses the response using a strict format:
   ```
   [USER]: message content
   [ASSISTANT]: response content
   [REASONING]: optional thinking
   ```
5. Creates a new Chat with the merged messages
6. Records the merge in MergeHistory

The merge preserves all insights, eliminates redundancy, and surfaces contradictions as alternatives.

## Environment Variables

Optional environment variables:

- `DATABASE_URL`: Override default SQLite path
- `SERVER_HOST`: Bind address (default: 0.0.0.0)
- `SERVER_PORT`: Port number (default: 8000)

## Development

### Logging

Logging is configured to INFO level. Adjust in `main.py` for debugging.

### Database Inspection

```bash
sqlite3 chat_app.db
sqlite> .tables
sqlite> SELECT * FROM chats;
```

### Running with Reload

The default `python main.py` runs with reload enabled. For production, use:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Error Handling

All endpoints return appropriate HTTP status codes:
- 201: Resource created
- 400: Bad request
- 404: Not found
- 500: Server error

Error responses include a `detail` field explaining the issue.

## Production Deployment

For production:

1. Set `reload=False` in uvicorn config
2. Use a proper ASGI server (Uvicorn, Gunicorn with uvicorn worker)
3. Configure CORS properly (don't allow all origins)
4. Store `.encryption_key` securely (environment variable or secrets manager)
5. Use a proper database (PostgreSQL with async driver)
6. Enable HTTPS/TLS
7. Add authentication/authorization
8. Implement rate limiting
9. Set up monitoring and logging

## License

MIT
