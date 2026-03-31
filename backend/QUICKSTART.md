# Quick Start Guide

## Prerequisites

- Python 3.13+
- PostgreSQL database running
- LiveKit server access (API key and secret)

## Setup Steps

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/voiceai
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_URL=wss://your-livekit-server.com
```

### 2. Run Database Migrations

```bash
# Generate the initial migration
uv run alembic revision --autogenerate -m "init sessions table"

# Apply migrations to database
uv run alembic upgrade head
```

### 3. Start the Server

```bash
uv run uvicorn src.main:app --reload
```

Server will start at: `http://localhost:8000`

### 4. Test the API

Visit the interactive API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Or test with curl:

```bash
# Health check
curl http://localhost:8000/

# Start a session
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "voice": {"provider": "elevenlabs", "voice_id": "abc123"},
    "agent": {"name": "custom-voice-stack", "instructions": "Be helpful"},
    "llm": {"model": "gpt-4", "temperature": 0.7}
  }'

# List sessions
curl http://localhost:8000/sessions
```

## Key Features

- **Singleton Configuration**: All secrets managed via Pydantic Settings with `@lru_cache` decorator
- **Clean MVC Architecture**: Separation of concerns across controller, service, and repository layers
- **Type Safety**: Pydantic schemas for request/response validation
- **Database Migrations**: Alembic for schema version control
- **LiveKit Integration**: Token generation and agent dispatch ready to use

## Troubleshooting

### Database Connection Error

Make sure PostgreSQL is running and credentials in `.env` are correct:

```bash
psql -U username -d voiceai -c "SELECT 1;"
```

### Missing Environment Variables

If you see validation errors on startup, ensure all required variables are set in `.env`:
- `DATABASE_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

### Import Errors

Make sure you're running commands with `uv run` prefix to use the virtual environment:

```bash
uv run uvicorn src.main:app --reload
```
