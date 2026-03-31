from fastapi import APIRouter
from src.controller.session_controller import SessionController
from src.schema.session import (
    StartSessionRequest,
    StartSessionResponse,
    UpdateSessionRequest,
    SessionResponse
)
from typing import List

router = APIRouter(prefix="/sessions", tags=["sessions"])
controller = SessionController()

router.post("/start", response_model=StartSessionResponse)(controller.start_session)
router.get("/", response_model=List[SessionResponse])(controller.list_sessions)
router.get("/{session_id}", response_model=SessionResponse)(controller.get_session)
router.patch("/{session_id}", response_model=SessionResponse)(controller.update_session)
