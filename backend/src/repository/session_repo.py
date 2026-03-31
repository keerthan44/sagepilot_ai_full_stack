from sqlalchemy.orm import Session as DBSession
from src.model.session import Session
from typing import List, Optional


class SessionRepository:

    def create(self, db: DBSession, session_id: str, agent_name: str, config: dict) -> Session:
        session = Session(
            id=session_id,
            agent_name=agent_name,
            config=config
        )
        db.add(session)
        db.flush()
        db.refresh(session)
        return session

    def list_all(self, db: DBSession) -> List[Session]:
        return db.query(Session).order_by(Session.created_at.desc()).all()

    def get(self, db: DBSession, session_id: str) -> Optional[Session]:
        return db.query(Session).filter(Session.id == session_id).first()

    def update(self, db: DBSession, session_id: str, transcript: list) -> Optional[Session]:
        session = self.get(db, session_id)
        if session:
            session.transcript = transcript
            db.flush()
            db.refresh(session)
        return session
