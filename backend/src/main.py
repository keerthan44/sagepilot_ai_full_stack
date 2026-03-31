from fastapi import FastAPI
from src.routes.session_routes import router as session_router
from src.core.db import engine, Base

app = FastAPI(title="Voice AI Backend", version="1.0.0")

app.include_router(session_router)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Voice AI Backend"}
