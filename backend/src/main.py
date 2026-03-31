from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes.session_routes import router as session_router
from src.core.db import engine, Base

app = FastAPI(title="Voice AI Backend", version="1.0.0")
origins = [
    "http://localhost:3000",  # frontend (Next.js, React, etc.)
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # or ["*"] for quick testing
    allow_credentials=True,
    allow_methods=["*"],            # GET, POST, etc.
    allow_headers=["*"],            # Authorization, Content-Type, etc.
)

app.include_router(session_router)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Voice AI Backend"}
