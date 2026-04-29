from __future__ import annotations

import base64
import json
from datetime import datetime
from urllib.parse import urlencode

import requests
import streamlit as st

API_BASE = "http://localhost:8000"
FRONTEND_URL = str(st.secrets["app"].get("frontend_url", "http://localhost:8501"))

FIREBASE_WEB_API_KEY = str(st.secrets["firebase_client"]["apiKey"])
GOOGLE_CLIENT_ID = str(st.secrets["app"]["google_client_id"])
GOOGLE_CLIENT_SECRET = str(st.secrets["app"]["google_client_secret"])
GOOGLE_REDIRECT_URI = str(st.secrets["app"]["google_redirect_uri"])
GOOGLE_SCOPES = str(st.secrets["app"].get("google_scopes", "openid email profile"))


def signup(email: str, password: str):
    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def login(email: str, password: str):
    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def sync_firebase_user(id_token: str):
    response = requests.post(f"{API_BASE}/sync-user", json={"id_token": id_token}, timeout=30)
    response.raise_for_status()
    return response.json()


def sync_google_user(email: str, google_id: str):
    response = requests.post(
        f"{API_BASE}/sync-user-google",
        json={"email": email, "google_id": google_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def build_google_authorization_url(state: str):
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_google_code(code: str):
    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    token_response.raise_for_status()
    token_data = token_response.json()

    def _decode_jwt_payload(token: str) -> dict:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {}
            payload = parts[1]
            padded = payload + "=" * (-len(payload) % 4)
            raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    access_token = token_data["access_token"]
    profile_response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    profile_response.raise_for_status()
    profile = profile_response.json()

    id_token_payload = _decode_jwt_payload(token_data.get("id_token", ""))
    email = profile.get("email") or id_token_payload.get("email") or ""
    google_id = profile.get("sub") or id_token_payload.get("sub") or ""
    name = profile.get("name") or id_token_payload.get("name") or ""

    if not email or not google_id:
        raise RuntimeError("Google profile is missing required email/sub information")

    return {
        "email": email,
        "google_id": google_id,
        "name": name,
    }


def _headers_for_user(user: dict | None):
    headers = {}
    if not user:
        return headers

    if user.get("provider") == "firebase" and user.get("idToken"):
        headers["Authorization"] = f"Bearer {user['idToken']}"
    elif user.get("provider") == "google":
        headers["X-User-Email"] = user.get("email", "")
        headers["X-User-Provider"] = "google"
    return headers


def _to_json_payload(payload: dict):
    serialized = {}
    for key, value in payload.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def create_paste(user: dict, payload: dict):
    response = requests.post(
        f"{API_BASE}/paste",
        json=_to_json_payload(payload),
        headers=_headers_for_user(user),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_paste(paste_id: str, user: dict | None = None):
    response = requests.get(f"{API_BASE}/paste/{paste_id}", headers=_headers_for_user(user), timeout=30)
    response.raise_for_status()
    return response.json()


def update_paste(paste_id: str, user: dict, payload: dict):
    response = requests.put(
        f"{API_BASE}/paste/{paste_id}",
        json=_to_json_payload(payload),
        headers=_headers_for_user(user),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def delete_paste(paste_id: str, user: dict):
    response = requests.delete(f"{API_BASE}/paste/{paste_id}", headers=_headers_for_user(user), timeout=30)
    response.raise_for_status()
    return response.json()


def my_pastes(user: dict):
    response = requests.get(f"{API_BASE}/my-pastes", headers=_headers_for_user(user), timeout=30)
    response.raise_for_status()
    return response.json()


def list_public_pastes(skip: int = 0, limit: int = 10, search: str | None = None):
    params = {"skip": skip, "limit": limit}
    if search:
        params["search"] = search
    response = requests.get(f"{API_BASE}/pastes", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_health():
    response = requests.get(f"{API_BASE}/health", timeout=30)
    response.raise_for_status()
    return response.json()
