from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FirebaseSyncRequest(BaseModel):
    id_token: str


class GoogleSyncRequest(BaseModel):
    email: str
    google_id: str


class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    email: str
    provider: str