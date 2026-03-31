from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class ToolCallItem(BaseModel):
    name: str
    args: Dict[str, Any]
    id: str


class ToolCallMetadata(BaseModel):
    name: str


class Message(BaseModel):
    role: str
    content: str
    timestamp: float
    tool_calls: Optional[List[ToolCallItem]] = None
    tool_call_id: Optional[str] = None
    metadata: Optional[ToolCallMetadata] = None


class StartSessionRequest(BaseModel):
    llm_provider: str
    llm_config: Optional[Dict[str, Any]] = None
    stt_provider: str
    stt_config: Optional[Dict[str, Any]] = None
    tts_provider: str
    tts_config: Optional[Dict[str, Any]] = None
    agent_name: str

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
