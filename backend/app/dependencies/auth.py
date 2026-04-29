from __future__ import annotations

from typing import Any

import requests
from fastapi import Header, HTTPException
from firebase_admin import auth as admin_auth

from backend.app.core.firebase_config import get_firebase_web_api_key, init_firebase_admin


def _verify_token_with_firebase_rest(token: str) -> dict[str, Any]:
    api_key = get_firebase_web_api_key()
    if not api_key:
        raise ValueError("FIREBASE_WEB_API_KEY is required for REST token verification fallback")

    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}",
        json={"idToken": token},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    users = data.get("users") or []
    if not users:
        raise ValueError("Token lookup returned no users")

    user = users[0]
    uid = user.get("localId")
    if not uid:
        raise ValueError("Token lookup returned invalid user payload")

    return {
        "uid": uid,
        "email": user.get("email"),
    }


def verify_firebase_id_token(token: str) -> dict[str, Any]:
    try:
        init_firebase_admin()
        return admin_auth.verify_id_token(token)
    except Exception:
        return _verify_token_with_firebase_rest(token)


def _decode_firebase_token(token: str) -> dict[str, Any]:
    decoded = verify_firebase_id_token(token)
    return {
        "userId": decoded.get("uid"),
        "uid": decoded.get("uid"),
        "email": decoded.get("email"),
        "provider": "firebase",
        "token": token,
    }


def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_provider: str | None = Header(default=None, alias="X-User-Provider"),
):
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = authorization.replace("Bearer ", "", 1).strip()
        try:
            return _decode_firebase_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if x_user_email and x_user_provider == "google":
        normalized_email = x_user_email.strip().lower()
        if not normalized_email:
            raise HTTPException(status_code=401, detail="Missing Google user email")

        return {
            "userId": normalized_email,
            "uid": normalized_email,
            "email": normalized_email,
            "provider": "google",
            "token": None,
        }

    raise HTTPException(status_code=401, detail="Authentication required")


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_provider: str | None = Header(default=None, alias="X-User-Provider"),
):
    try:
        return get_current_user(
            authorization=authorization,
            x_user_email=x_user_email,
            x_user_provider=x_user_provider,
        )
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise