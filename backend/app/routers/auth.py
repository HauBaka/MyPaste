from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies.auth import get_current_user, verify_firebase_id_token
from backend.app.schemas.auth import FirebaseSyncRequest, GoogleSyncRequest, UserResponse
from backend.app.services.firestore_service import sync_firebase_user, sync_google_user

router = APIRouter(tags=["auth"])


@router.post("/sync-user", response_model=UserResponse)
def sync_user(payload: FirebaseSyncRequest):
    """Đồng bộ từ Firebase ID token. Nếu user chưa tồn tại trong Firestore thì sẽ được tạo mới."""
    try:
        decoded = verify_firebase_id_token(payload.id_token)
        user = sync_firebase_user(user_id=decoded["uid"], email=decoded.get("email", ""))
        return UserResponse(**user)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {exc}") from exc


@router.post("/sync-user-google", response_model=UserResponse)
def sync_user_google(payload: GoogleSyncRequest):
    """Đồng bộ user Google. Nếu user chưa tồn tại trong Firestore thì sẽ được tạo mới."""
    try:
        user = sync_google_user(email=payload.email, google_id=payload.google_id)
        return UserResponse(**user)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "userId": user["userId"],
        "email": user["email"],
        "provider": user["provider"],
    }