from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class Message(BaseModel):
    role: str
    content: str
    tool_call: Optional[Dict[str, Any]] = None


class StartSessionRequest(BaseModel):
    voice: dict
    agent: dict
    llm: Optional[dict] = None


class StartSessionResponse(BaseModel):
    session_id: str
    token: str
    room_name: str


class UpdateSessionRequest(BaseModel):
    transcript: List[Message]


class SessionResponse(BaseModel):
    id: str
    agent_name: str
    config: Optional[dict] = None
    transcript: Optional[List[Message]] = None
    created_at: datetime
