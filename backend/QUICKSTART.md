# Quick Start Guide

Get the Chat Merge App backend running in 5 minutes.

## 1. Setup Environment

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure API Keys

```bash
# Copy example to .env
cp .env.example .env

# Edit .env with your keys
nano .env  # or use your editor
```

You'll need at least one API key. Get them from:
- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/
- **Google Gemini**: https://aistudio.google.com/app/apikey

## 3. Start Server

```bash
python main.py
```

Server runs at `http://localhost:8000`

Check health: `curl http://localhost:8000/health`

## 4. API Documentation

Visit `http://localhost:8000/docs` for interactive API docs (Swagger UI)

## Basic Usage

### Create a Chat

```bash
CHAT_ID=$(curl -s -X POST http://localhost:8000/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Chat",
    "provider": "openai",
    "model": "gpt-4o"
  }' | jq -r '.id')

echo $CHAT_ID
```

### Send a Message & Get Response

```bash
curl -N http://localhost:8000/api/chats/$CHAT_ID/completions \
  -H "Content-Type: application/json" \
  -d '{"content": "What is Python?"}'
```

The `-N` flag disables buffering to see streaming events in real-time.

Each line is a JSON event with `type` and `data`.

### List All Chats

```bash
curl http://localhost:8000/api/chats/ | jq
```

### Get Chat with Messages

```bash
curl http://localhost:8000/api/chats/$CHAT_ID | jq
```

## API Key Management

### Store API Key

```bash
curl -X POST http://localhost:8000/api/api-keys/ \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-..."
  }'
```

### List Stored Keys

```bash
curl http://localhost:8000/api/api-keys/ | jq
```

Note: The actual keys are never returned, only provider names and status.

## Merge Conversations

### Create Multiple Chats

```bash
# Create chat 1
CHAT1=$(curl -s -X POST http://localhost:8000/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Chat 1",
    "provider": "openai",
    "model": "gpt-4o"
  }' | jq -r '.id')

# Create chat 2
CHAT2=$(curl -s -X POST http://localhost:8000/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Chat 2",
    "provider": "openai",
    "model": "gpt-4o"
  }' | jq -r '.id')
```

### Add Some Messages

```bash
# Chat 1
curl -N http://localhost:8000/api/chats/$CHAT1/completions \
  -H "Content-Type: application/json" \
  -d '{"content": "What is machine learning?"}'

# Chat 2
curl -N http://localhost:8000/api/chats/$CHAT2/completions \
  -H "Content-Type: application/json" \
  -d '{"content": "Explain neural networks"}'
```

### Merge Them

```bash
curl -N http://localhost:8000/api/merge \
  -H "Content-Type: application/json" \
  -d '{
    "chat_ids": ["'$CHAT1'", "'$CHAT2'"],
    "merge_provider": "openai",
    "merge_model": "gpt-4o"
  }'
```

Look for the `merge_complete` event in the stream - its data field contains the merged chat ID.

## Available Models

```bash
curl http://localhost:8000/api/models | jq
```

Response:
```json
{
  "openai": ["gpt-4o", "gpt-4o-mini", ...],
  "anthropic": ["claude-sonnet-4-20250514", ...],
  "gemini": ["gemini-2.0-flash", ...]
}
```

## Database

SQLite database is in `chat_app.db`. To inspect:

```bash
sqlite3 chat_app.db
sqlite> .tables
sqlite> SELECT id, title, provider, model FROM chats;
sqlite> .quit
```

## Troubleshooting

### No API key configured error

Make sure you've:
1. Created .env file with API keys
2. Called POST /api/api-keys/ to store them in the database

### Connection refused

Make sure the server is running: `python main.py`

### Import errors

Make sure all dependencies are installed: `pip install -r requirements.txt`

### Database locked error

Delete `chat_app.db` and restart (you'll lose data):
```bash
rm chat_app.db
python main.py
```

## Next Steps

- Read the full [README.md](README.md) for architecture details
- Check out the API docs at `/docs`
- Build a frontend to consume these endpoints
- Deploy to production (see README for production setup)

## Need Help?

- Check logs: Look at console output from `python main.py`
- API docs: Visit `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`
