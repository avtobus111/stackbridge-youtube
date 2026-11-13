import time
import uuid
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    handle: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(12), default="user")
    color: Mapped[str] = mapped_column(String(7), default="#065fd4")
    created_at: Mapped[float] = mapped_column(default=time.time)
    __table_args__ = (CheckConstraint("role IN ('user', 'moderator', 'admin')"),)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[float] = mapped_column(index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    window: Mapped[float]


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="Разное")
    visibility: Mapped[str] = mapped_column(String(10), default="public")
    status: Mapped[str] = mapped_column(String(12), default="uploading")
    hidden: Mapped[bool] = mapped_column(default=False)
    moderation_reason: Mapped[str] = mapped_column(String(500), default="")
    error: Mapped[str] = mapped_column(String(300), default="")
    source_key: Mapped[str] = mapped_column(String(200), default="")
    media_key: Mapped[str] = mapped_column(String(200), default="")
    thumbnail_key: Mapped[str] = mapped_column(String(200), default="")
    duration: Mapped[float] = mapped_column(default=0)
    size: Mapped[int] = mapped_column(default=0)
    views: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_at: Mapped[float] = mapped_column(default=0)
    created_at: Mapped[float] = mapped_column(default=time.time, index=True)
    updated_at: Mapped[float] = mapped_column(default=time.time)
    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'private')"),
        CheckConstraint("status IN ('uploading','receiving','queued','processing','ready','failed')"),
        Index("ix_videos_queue", "status", "lease_at"),
    )


class Grant(Base):
    __tablename__ = "grants"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Like(Base):
    __tablename__ = "likes"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class ViewEvent(Base):
    __tablename__ = "view_events"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    viewer_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[float] = mapped_column(default=time.time)


class Subscription(Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    __table_args__ = (CheckConstraint("user_id != channel_id"),)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[float] = mapped_column(default=time.time)


class Playlist(Base):
    __tablename__ = "playlists"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    visibility: Mapped[str] = mapped_column(String(10), default="public")
    created_at: Mapped[float] = mapped_column(default=time.time)
    __table_args__ = (CheckConstraint("visibility IN ('public','private')"),)


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    playlist_id: Mapped[str] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[float] = mapped_column(default=time.time)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(500))
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[float] = mapped_column(default=time.time)
    __table_args__ = (UniqueConstraint("video_id", "user_id"),)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[float] = mapped_column(default=time.time)
