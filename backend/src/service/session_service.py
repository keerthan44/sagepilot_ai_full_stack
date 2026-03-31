import uuid
from sqlalchemy.orm import Session as DBSession
from src.repository.session_repo import SessionRepository
from src.core.livekit import create_access_token, dispatch_agent
from src.schema.session import StartSessionRequest, UpdateSessionRequest
from src.model.session import Session
from typing import List, Optional


class SessionService:

    def __init__(self):
        self.repo = SessionRepository()

    def start_session(self, db: DBSession, req: StartSessionRequest) -> dict:
        session_id = str(uuid.uuid4())
        room_name = f"room_{session_id}"

        session = self.repo.create(
            db=db,
            session_id=session_id,
            agent_name=req.agent["name"],
            config=req.model_dump()
        )

        token = create_access_token(
            identity=session_id,
            room=room_name
        )

        dispatch_agent(
            room_name=room_name,
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
