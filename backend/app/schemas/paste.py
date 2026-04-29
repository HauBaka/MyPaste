from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PasteCreateRequest(BaseModel):
    title: str
    content: str = Field(min_length=1, max_length=2048)
    language: str = "text"
    visibility: Literal["public", "private"] = "public"
    custom_id: str | None = Field(default=None, alias="customId")

    model_config = ConfigDict(populate_by_name=True)


class PasteUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = Field(default=None, max_length=2048)
    language: str | None = None
    visibility: Literal["public", "private"] | None = None

    model_config = ConfigDict(populate_by_name=True)


class PasteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str = Field(alias="userId")
    title: str
    content: str
    language: str
    visibility: str
    created_at: datetime = Field(alias="createdAt")
    is_expired: bool = Field(alias="isExpired")
    can_edit: bool = Field(alias="canEdit")
