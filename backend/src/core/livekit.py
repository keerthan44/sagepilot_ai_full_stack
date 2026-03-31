import json
from livekit import api
from src.core.config import get_settings

settings = get_settings()


def create_access_token(identity: str, room: str) -> str:
    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(api.VideoGrants(room_join=True, room=room))
    
    return token.to_jwt()


async def dispatch_agent(room_name: str, agent_name: str, metadata: dict) -> dict:
    lkapi = api.LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET
    )
    
    try:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room_name,
                metadata=json.dumps(metadata)
            )
        )
        
        return {
            "dispatch_id": dispatch.id,
            "agent_name": dispatch.agent_name,
            "room": dispatch.room
        }
    finally:
        await lkapi.aclose()
