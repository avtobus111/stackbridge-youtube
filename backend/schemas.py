from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(StrictModel):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=128)


class Login(StrictModel):
    handle: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class VideoInput(StrictModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=5000)
    category: str = Field(default="Разное", min_length=1, max_length=40)
    visibility: Literal["public", "private"] = "public"


class GrantInput(StrictModel):
    handles: list[str] = Field(max_length=100)

    @field_validator("handles")
    @classmethod
    def valid_handles(cls, values):
        if any(not x or len(x) > 32 for x in values):
            raise ValueError("Некорректный логин")
        return list(dict.fromkeys(x.lower().strip() for x in values))


class CommentInput(StrictModel):
    body: str = Field(min_length=1, max_length=2000)


class PlaylistInput(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    visibility: Literal["public", "private"] = "public"


class ReportInput(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class ModerationInput(StrictModel):
    hidden: bool
    reason: str = Field(min_length=3, max_length=500)


class RoleInput(StrictModel):
    role: Literal["user", "moderator", "admin"]


class ChannelInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
