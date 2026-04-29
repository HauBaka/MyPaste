from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
import streamlit as st

from backend.app.dependencies.auth import get_current_user, get_current_user_optional
from backend.app.schemas.paste import PasteCreateRequest, PasteResponse, PasteUpdateRequest
from backend.app.services.firestore_service import create_paste, delete_paste, get_paste, list_public_pastes, list_user_pastes, update_paste

router = APIRouter(tags=["pastes"])


@router.get("/p/{paste_id}")
def paste_redirect(paste_id: str):
    frontend_url = str(st.secrets["app"].get("frontend_url", "http://localhost:8501"))
    separator = "&" if "?" in frontend_url else "?"
    return RedirectResponse(url=f"{frontend_url}{separator}p={paste_id}", status_code=302)


@router.post("/paste", response_model=PasteResponse)
def create_paste_endpoint(payload: PasteCreateRequest, user=Depends(get_current_user)):
    try:
        paste = create_paste(owner_id=user["userId"], payload=payload.model_dump(by_alias=False))
        return PasteResponse(**paste)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/paste/{paste_id}", response_model=PasteResponse)
def get_paste_endpoint(paste_id: str, user=Depends(get_current_user_optional)):
    paste = get_paste(paste_id, current_user=user)
    if not paste:
        raise HTTPException(status_code=404, detail="Paste not found")
    return PasteResponse(**paste)


@router.get("/my-pastes", response_model=List[PasteResponse])
def my_pastes(user=Depends(get_current_user)):
    return list_user_pastes(user["userId"])


@router.get("/pastes", response_model=List[PasteResponse])
def list_pastes(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100), search: str | None = None):
    return list_public_pastes(skip=skip, limit=limit, search=search)


@router.put("/paste/{paste_id}", response_model=PasteResponse)
def update_paste_endpoint(paste_id: str, payload: PasteUpdateRequest, user=Depends(get_current_user)):
    try:
        updated = update_paste(paste_id, current_user=user, payload=payload.model_dump(by_alias=False, exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail="Paste not found")
        return PasteResponse(**updated)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/paste/{paste_id}")
def delete_paste_endpoint(paste_id: str, user=Depends(get_current_user)):
    try:
        if not delete_paste(paste_id, current_user=user):
            raise HTTPException(status_code=404, detail="Paste not found")
        return {"message": "Paste deleted"}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
