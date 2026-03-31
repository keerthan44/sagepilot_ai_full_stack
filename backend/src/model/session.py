from sqlalchemy import Column, String, DateTime, JSON
from datetime import datetime
import uuid
from src.core.db import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String, nullable=False)
    config = Column(JSON, nullable=True)
    transcript = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
