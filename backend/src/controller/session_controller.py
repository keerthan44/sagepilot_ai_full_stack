from fastapi import Depends
from sqlalchemy.orm import Session as DBSession
from typing import List

from src.service.session_service import SessionService
from src.schema.session import (
    StartSessionRequest,
    StartSessionResponse,
    UpdateSessionRequest,
    SessionResponse
)
from src.core.db import get_db


class SessionController:
    
    def __init__(self):
        self.service = SessionService()
    
    async def start_session(self, req: StartSessionRequest, db: DBSession = Depends(get_db)) -> StartSessionResponse:
        result = await self.service.start_session(db, req)
        return StartSessionResponse(**result)
    
    def list_sessions(self, db: DBSession = Depends(get_db)) -> List[SessionResponse]:
        sessions = self.service.list_sessions(db)
        return [
            SessionResponse(
                id=s.id,
                agent_name=s.agent_name,
                config=s.config,
                transcript=s.transcript,
                created_at=s.created_at
            ) for s in sessions
        ]
    
    def get_session(self, session_id: str, db: DBSession = Depends(get_db)) -> SessionResponse:
        session = self.service.get_session(db, session_id)
        if not session:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SessionResponse(
            id=session.id,
            agent_name=session.agent_name,
            config=session.config,
            transcript=session.transcript,
            created_at=session.created_at
        )
    
    def update_session(
        self,
        session_id: str,
        req: UpdateSessionRequest,
        db: DBSession = Depends(get_db)
    ) -> SessionResponse:
        session = self.service.update_session(db, session_id, req)
        if not session:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SessionResponse(
            id=session.id,
            agent_name=session.agent_name,
            config=session.config,
            transcript=session.transcript,
            created_at=session.created_at
        )
