# Voice AI Backend - FastAPI MVC

A clean, minimal backend using FastAPI with MVC architecture, SQLAlchemy, Alembic, and LiveKit integration.

## Architecture

- **Controller Layer**: FastAPI route handlers
- **Service Layer**: Business logic and orchestration  
- **Repository Layer**: Database access patterns
- **Models**: SQLAlchemy ORM models
- **Schemas**: Pydantic request/response validation

## Project Structure

```
backend/
├── src/
│   ├── main.py                    # FastAPI app entry point
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (singleton)
│   │   ├── db.py                  # Database engine & session
│   │   └── livekit.py             # LiveKit utilities
│   ├── model/
│   │   └── session.py             # SQLAlchemy models
│   ├── schema/
│   │   └── session.py             # Pydantic schemas
│   ├── repository/
│   │   └── session_repo.py        # Database access layer
│   ├── service/
│   │   └── session_service.py     # Business logic
│   ├── controller/
│   │   └── session_controller.py  # Request handlers
│   └── routes/
│       └── session_routes.py      # Route definitions
├── alembic/                       # Migration files
├── alembic.ini                    # Alembic config
├── .env.example                   # Environment template
└── pyproject.toml                 # Dependencies
```

## Setup

### Option 1: Docker (Recommended)

See [DOCKER.md](DOCKER.md) for complete Docker setup instructions.

**Quick start**:

```bash
# Create .env file with your LiveKit credentials
cp .env.example .env

# Start with docker-compose
docker-compose -f docker-compose.example.yml up -d
```

API will be available at `http://localhost:8000`

### Option 2: Local Development

#### 1. Install uv (if not already installed)

```bash
pip install uv
```

#### 2. Install dependencies

```bash
uv sync
```

#### 3. Configure environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/voiceai
LIVEKIT_API_KEY=your_actual_api_key
LIVEKIT_API_SECRET=your_actual_api_secret
LIVEKIT_URL=wss://your-livekit-server.com
```

### 4. Run database migrations

```bash
# Generate initial migration
uv run alembic revision --autogenerate -m "init sessions table"

# Apply migrations
uv run alembic upgrade head
```

### 5. Start the server

```bash
uv run uvicorn src.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
```
GET /
```

### Sessions

#### Start a new session
```
POST /sessions/start
```

Request body:
```json
{
  "voice": {
    "provider": "elevenlabs",
    "voice_id": "..."
  },
  "agent": {
    "name": "custom-voice-stack",
    "instructions": "..."
  },
  "llm": {
    "model": "gpt-4",
    "temperature": 0.7
  }
}
```

Response:
```json
{
  "session_id": "uuid",
  "token": "livekit_jwt_token",
  "room_name": "room_uuid"
}
```

#### List all sessions
```
GET /sessions
```

#### Get a specific session
```
GET /sessions/{session_id}
```

#### Update session transcript
```
PATCH /sessions/{session_id}
```

Request body:
```json
{
  "transcript": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "tool_calls": [
    {
      "name": "search",
      "input": {"query": "weather"},
      "output": {"result": "sunny"}
    }
  ]
}
```

## Configuration (Singleton Pattern)

The application uses Pydantic Settings with a singleton pattern for configuration management:

- All secrets are loaded from environment variables
- Settings are validated at startup
- Single instance is cached and reused throughout the app lifecycle
- Type-safe access to configuration values

## Development

### View API documentation

FastAPI provides automatic interactive API docs:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Create new migrations

After modifying models:

```bash
uv run alembic revision --autogenerate -m "description of changes"
uv run alembic upgrade head
```

### Rollback migrations

```bash
uv run alembic downgrade -1
```

## Technologies

- **FastAPI**: Web framework
- **SQLAlchemy**: ORM
- **Alembic**: Database migrations
- **Pydantic**: Data validation and settings
- **PostgreSQL**: Database
- **LiveKit**: Real-time voice/video
- **uv**: Dependency and environment management
