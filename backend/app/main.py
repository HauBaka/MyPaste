from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import streamlit as st

from backend.app.routers.auth import router as auth_router
from backend.app.routers.pastes import router as paste_router
from backend.app.services.firestore_service import get_system_stats

app = FastAPI(title="MyPaste Backend")

_STARTED_AT = datetime.now(timezone.utc)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(paste_router)


@app.get("/health")
def health():
    return get_system_stats(_STARTED_AT)
