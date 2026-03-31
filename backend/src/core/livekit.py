from livekit import api
from src.core.config import get_settings

settings = get_settings()


def create_access_token(identity: str, room: str) -> str:
    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(api.VideoGrants(room_join=True, room=room))
    
    return token.to_jwt()


def dispatch_agent(room_name: str, metadata: dict) -> dict:
    return {
        "agent_name": "custom-voice-stack",
        "room": room_name,
        "metadata": metadata
    }
