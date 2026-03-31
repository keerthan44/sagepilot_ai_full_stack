import uuid
from sqlalchemy.orm import Session as DBSession
from src.repository.session_repo import SessionRepository
from src.core.livekit import create_access_token, dispatch_agent
from src.schema.session import StartSessionRequest, UpdateSessionRequest
from src.model.session import Session
from typing import List, Optional
from fastapi import HTTPException


class SessionService:

    def __init__(self):
        self.repo = SessionRepository()

    def _validate_config(self, req: StartSessionRequest):
        stt_provider = req.stt_provider.lower()
        llm_provider = req.llm_provider.lower()
        tts_provider = req.tts_provider.lower()
        
        if stt_provider == "deepgram":
            if not req.stt_config:
                req.stt_config = {
                    "model": "nova-3",
                    "language": "en",
                    "transport": "websocket"
                }
            required_keys = ["model", "language", "transport"]
            if not all(k in req.stt_config for k in required_keys):
                raise HTTPException(
                    status_code=400,
                    detail=f"Deepgram STT requires: {required_keys}"
                )
        
        elif stt_provider == "assemblyai":
            if not req.stt_config:
                req.stt_config = {"model": "universal-streaming-english"}
            if "model" not in req.stt_config:
                raise HTTPException(
                    status_code=400,
                    detail="AssemblyAI STT requires 'model' in config"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported STT provider: {stt_provider}. Supported: deepgram, assemblyai"
            )
        
        if llm_provider == "openai":
            if not req.llm_config:
                req.llm_config = {
                    "model": "gpt-4.1-mini",
                    "temperature": 0.7
                }
            required_keys = ["model", "temperature"]
            if not all(k in req.llm_config for k in required_keys):
                raise HTTPException(
                    status_code=400,
                    detail=f"OpenAI LLM requires: {required_keys}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported LLM provider: {llm_provider}. Only 'openai' is supported"
            )
        
        if tts_provider == "elevenlabs":
            if not req.tts_config:
                req.tts_config = {
                    "model": "eleven_flash_v2_5",
                    "voice": "hpp4J3VqNfWAUOO0d1Us",
                    "transport": "http"
                }
            required_keys = ["model", "voice", "transport"]
            if not all(k in req.tts_config for k in required_keys):
                raise HTTPException(
                    status_code=400,
                    detail=f"ElevenLabs TTS requires: {required_keys}"
                )
        
        elif tts_provider == "cartesia":
            if not req.tts_config:
                req.tts_config = {
                    "model": "sonic-3",
                    "voice": "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
                    'language': 'en',
                    "transport": "http"
                }
            required_keys = ["model", "voice", "transport"]
            if not all(k in req.tts_config for k in required_keys):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cartesia TTS requires: {required_keys}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported TTS provider: {tts_provider}. Supported: elevenlabs, cartesia"
            )

    async def start_session(self, db: DBSession, req: StartSessionRequest) -> dict:
        self._validate_config(req)
        
        session_id = str(uuid.uuid4())
        room_name = f"room_{session_id}"

        session = self.repo.create(
            db=db,
            session_id=session_id,
            agent_name=req.agent_name,
            config=req.model_dump()
        )

        token = create_access_token(
            identity=session_id,
            room=room_name
        )

        dispatch_result = await dispatch_agent(
            room_name=room_name,
            agent_name='custom-voice-stack',
            metadata={
                "session_id": session_id,
                "config": req.model_dump()
            }
        )

        return {
            "session_id": session_id,
            "token": token,
            "room_name": room_name
        }

    def list_sessions(self, db: DBSession) -> List[Session]:
        return self.repo.list_all(db)

    def get_session(self, db: DBSession, session_id: str) -> Optional[Session]:
        return self.repo.get(db, session_id)

    def update_session(self, db: DBSession, session_id: str, req: UpdateSessionRequest) -> Optional[Session]:
        return self.repo.update(
            db,
            session_id,
            transcript=[msg.model_dump() for msg in req.transcript]
        )
