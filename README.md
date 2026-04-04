# Setup

## Prerequisites

- Docker & Docker Compose installed

---

## 1. Populate env files

### `backend/.env.prod`

```env
LIVEKIT_API_KEY="..."
LIVEKIT_API_SECRET="..."
LIVEKIT_URL="wss://..."
```

### `frontend/trial1/.env.prod`

```env
AGENT_NAME="custom-voice-stack"
LIVEKIT_API_KEY="..."
LIVEKIT_API_SECRET="..."
LIVEKIT_URL="wss://..."
NEXT_PUBLIC_LIVEKIT_URL="wss://..."
NEXT_PUBLIC_APP_CONFIG_ENDPOINT=""
SANDBOX_ID=""
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### `livekit/.env.prod`

```env
LIVEKIT_API_KEY="..."
LIVEKIT_API_SECRET="..."
LIVEKIT_URL="wss://..."
OPENAI_API_KEY="..."
ELEVEN_API_KEY="..."
DEEPGRAM_API_KEY="..."
ASSEMBLYAI_API_KEY="..."
CARTESIA_API_KEY="..."
API_BASE_URL="http://backend:8000"   # must stay as-is for Docker networking
```

> `API_BASE_URL` must be `http://backend:8000` — this is the internal Docker service name, not localhost.

---

## 2. Run

```bash
docker compose up --build
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:3000      |
| Backend  | http://localhost:8000      |
| Logs     | http://localhost:9999      |

# Demo

You can view the demo video: https://youtu.be/KZI5R5BLuog
