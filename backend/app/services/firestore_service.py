from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from firebase_admin import firestore

from backend.app.core.firebase_config import get_firestore

def _db():
    return get_firestore()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_paste_id(custom_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", custom_id.strip()).strip("-")
    return cleaned[:80]


def _paste_ref(paste_id: str):
    return _db().collection("pastes").document(paste_id)


def ensure_user(user_id: str, email: str, provider: str, google_id: str | None = None):
    ref = _db().collection("users").document(user_id)
    payload = {
        "email": _normalize_email(email),
        "provider": provider,
        "createdAt": _now(),
    }
    if google_id:
        payload["googleId"] = google_id

    if ref.get().exists:
        ref.set(payload, merge=True)
    else:
        ref.set(payload)

    return {
        "userId": user_id,
        "email": payload["email"],
        "provider": provider,
    }


def sync_firebase_user(user_id: str, email: str):
    return ensure_user(user_id=user_id, email=email, provider="firebase")


def sync_google_user(email: str, google_id: str):
    normalized_email = _normalize_email(email)
    normalized_google_id = (google_id or "").strip()

    if not normalized_email:
        raise ValueError("Google profile does not contain email")

    if not normalized_google_id:
        raise ValueError("Google profile does not contain google_id")

    return ensure_user(user_id=normalized_email, email=normalized_email, provider="google", google_id=normalized_google_id)


def _serialize_paste(snapshot, current_user: dict | None = None):
    if not snapshot.exists:
        return None

    data = snapshot.to_dict()
    created_at = data.get("createdAt")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            created_at = _now()
    if created_at is None:
        created_at = _now()

    is_owner = bool(current_user and data.get("userId") == current_user.get("userId"))

    if data.get("visibility") == "private" and not is_owner:
        return None

    return {
        "id": snapshot.id,
        "userId": str(data.get("userId") or "unknown"),
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "language": data.get("language", "text"),
        "visibility": data.get("visibility", "public"),
        "createdAt": created_at,
        "isExpired": False,
        "canEdit": is_owner,
    }


def create_paste(owner_id: str, payload: dict):
    custom_id = payload.get("custom_id")
    if custom_id:
        paste_id = _normalize_paste_id(custom_id)
        if not paste_id:
            raise ValueError("Custom ID cannot be empty")
    else:
        paste_id = uuid.uuid4().hex[:12]

    ref = _paste_ref(paste_id)
    if ref.get().exists:
        raise ValueError("Paste ID already exists")

    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Title is required")

    content = payload.get("content") or ""
    if not content.strip():
        raise ValueError("Content is required")
    if len(content) > 2048:
        raise ValueError("Content must be 2048 characters or less")

    data = {
        "userId": owner_id,
        "title": title,
        "content": content,
        "language": (payload.get("language") or "text").strip() or "text",
        "visibility": payload.get("visibility", "public"),
        "createdAt": _now(),
    }
    ref.set(data)

    return {
        "id": paste_id,
        **data,
        "isExpired": False,
        "canEdit": True,
    }


def get_paste(paste_id: str, current_user: dict | None = None):
    return _serialize_paste(_paste_ref(paste_id).get(), current_user=current_user)


def list_user_pastes(user_id: str):
    query = (
        _db().collection("pastes")
        .where("userId", "==", user_id)
        .order_by("createdAt", direction="DESCENDING")
    )
    return [
        item
        for snapshot in query.stream()
        if (item := _serialize_paste(snapshot, current_user={"userId": user_id}))
    ]


def list_public_pastes(skip: int = 0, limit: int = 10, search: str | None = None):
    def _created_at_sort_value(item: dict) -> datetime:
        value = item.get("createdAt")
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    all_results = []
    for snapshot in _db().collection("pastes").stream():
        item = _serialize_paste(snapshot)
        if not item:
            continue
        if item.get("visibility") != "public":
            continue
        all_results.append(item)

    if search:
        search_lower = search.strip().lower()
        all_results = [item for item in all_results if search_lower in item["id"].lower()]

    all_results.sort(key=_created_at_sort_value, reverse=True)
    return all_results[skip : skip + limit]


def update_paste(paste_id: str, current_user: dict, payload: dict):
    ref = _paste_ref(paste_id)
    snapshot = ref.get()
    if not snapshot.exists:
        return None

    current = snapshot.to_dict()
    if not current:
        return None
    
    if current.get("userId") != current_user.get("userId"):
        raise PermissionError("You do not own this paste")

    updates: dict = {}

    for field in ("title", "content", "language", "visibility"):
        value = payload.get(field)
        if value is not None:
            updates[field] = value.strip() if isinstance(value, str) else value

    if "content" in updates and len(updates["content"]) > 2048:
        raise ValueError("Content must be 2048 characters or less")

    if not updates:
        return _serialize_paste(snapshot, current_user=current_user)

    ref.set(updates, merge=True)
    return _serialize_paste(ref.get(), current_user=current_user)


def delete_paste(paste_id: str, current_user: dict):
    ref = _paste_ref(paste_id)
    snapshot = ref.get()
    if not snapshot.exists:
        return False

    current = snapshot.to_dict()
    if not current:
        return False

    if current.get("userId") != current_user.get("userId"):
        raise PermissionError("You do not own this paste")

    ref.delete()
    return True


def get_system_stats(started_at: datetime):
    users = 0
    total_pastes = 0
    public_pastes = 0
    status = "ok"
    error = ""

    try:
        for _ in _db().collection("users").stream():
            users += 1

        for snapshot in _db().collection("pastes").stream():
            total_pastes += 1
            data = snapshot.to_dict() or {}
            if data.get("visibility", "public") == "public":
                public_pastes += 1
    except Exception as exc:
        status = "degraded"
        error = str(exc)

    uptime_seconds = int(max((_now() - started_at).total_seconds(), 0))
    return {
        "status": status,
        "uptimeSeconds": uptime_seconds,
        "totalUsers": users,
        "totalPastes": total_pastes,
        "publicPastes": public_pastes,
        "error": error,
    }

