from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Video, Like, Subscription, Comment, Playlist, PlaylistItem, Report, Audit
from .schemas import CommentInput, PlaylistInput, ReportInput, ModerationInput, RoleInput
from .security import current_user, require_user, require_csrf, require_moderator, user_json
from .videos import get_video, can_view, video_json, count

router = APIRouter(prefix="/api", tags=["Social and moderation"])


def commit_unique(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


@router.put("/videos/{video_id}/like")
def like(video_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    get_video(video_id, user, db)
    if not db.get(Like, (video_id, user.id)):
        db.add(Like(video_id=video_id, user_id=user.id))
        commit_unique(db)
    return {"liked": True, "likes": count(db, Like, Like.video_id == video_id)}


@router.delete("/videos/{video_id}/like")
def unlike(video_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    get_video(video_id, user, db)
    db.execute(delete(Like).where(Like.video_id == video_id, Like.user_id == user.id))
    db.commit()
    return {"liked": False, "likes": count(db, Like, Like.video_id == video_id)}


@router.get("/videos/{video_id}/comments")
def comments(
    video_id: str, offset: int = Query(0, ge=0), user=Depends(current_user), db: Session = Depends(get_db)
):
    get_video(video_id, user, db)
    rows = db.scalars(
        select(Comment)
        .where(Comment.video_id == video_id)
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(100)
    ).all()
    return {
        "items": [
            {
                "id": c.id,
                "body": c.body,
                "created_at": c.created_at,
                "author": user_json(db.get(User, c.user_id)),
                "can_delete": bool(user and (user.id == c.user_id or user.role in ("admin", "moderator"))),
            }
            for c in rows
        ]
    }


@router.post("/videos/{video_id}/comments", status_code=201)
def comment(video_id: str, data: CommentInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    get_video(video_id, user, db)
    c = Comment(video_id=video_id, user_id=user.id, body=data.body)
    db.add(c)
    db.commit()
    return {
        "id": c.id,
        "body": c.body,
        "created_at": c.created_at,
        "author": user_json(user),
        "can_delete": True,
    }


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    c = db.get(Comment, comment_id)
    if not c:
        raise HTTPException(404, "Комментарий не найден")
    get_video(c.video_id, user, db)
    if user.id != c.user_id and user.role not in ("admin", "moderator"):
        raise HTTPException(403, "Недостаточно прав")
    db.delete(c)
    db.commit()


@router.put("/channels/{handle}/subscription")
def subscribe(handle: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    channel = db.scalar(select(User).where(User.handle == handle.lower()))
    if not channel:
        raise HTTPException(404, "Канал не найден")
    if user.id == channel.id:
        raise HTTPException(422, "Нельзя подписаться на свой канал")
    if not db.get(Subscription, (user.id, channel.id)):
        db.add(Subscription(user_id=user.id, channel_id=channel.id))
        commit_unique(db)
    return {"subscribed": True, "subscribers": count(db, Subscription, Subscription.channel_id == channel.id)}


@router.delete("/channels/{handle}/subscription")
def unsubscribe(handle: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    channel = db.scalar(select(User).where(User.handle == handle.lower()))
    if not channel:
        raise HTTPException(404, "Канал не найден")
    db.execute(
        delete(Subscription).where(Subscription.user_id == user.id, Subscription.channel_id == channel.id)
    )
    db.commit()
    return {
        "subscribed": False,
        "subscribers": count(db, Subscription, Subscription.channel_id == channel.id),
    }


@router.get("/subscriptions")
def subscriptions(user=Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(User)
        .join(Subscription, Subscription.channel_id == User.id)
        .where(Subscription.user_id == user.id)
    ).all()
    return {"items": [user_json(u) for u in rows]}


@router.get("/playlists")
def my_playlists(user=Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Playlist).where(Playlist.owner_id == user.id).order_by(Playlist.created_at.desc())
    ).all()
    return {"items": [{"id": p.id, "title": p.title, "visibility": p.visibility} for p in rows]}


@router.post("/playlists", status_code=201)
def create_playlist(data: PlaylistInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    p = Playlist(owner_id=user.id, **data.model_dump())
    db.add(p)
    db.commit()
    return {"id": p.id, "title": p.title, "visibility": p.visibility}


def get_playlist(playlist_id, user, db, owner=False):
    p = db.get(Playlist, playlist_id)
    if not p or (p.visibility == "private" and (not user or p.owner_id != user.id)):
        raise HTTPException(404, "Плейлист не найден")
    if owner and (not user or p.owner_id != user.id):
        raise HTTPException(403, "Изменять плейлист может только владелец")
    return p


@router.get("/playlists/{playlist_id}")
def playlist_detail(playlist_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    p = get_playlist(playlist_id, user, db)
    rows = db.scalars(
        select(Video)
        .join(PlaylistItem, PlaylistItem.video_id == Video.id)
        .where(PlaylistItem.playlist_id == p.id)
        .order_by(PlaylistItem.added_at)
    ).all()
    return {
        "id": p.id,
        "title": p.title,
        "visibility": p.visibility,
        "owner": user_json(db.get(User, p.owner_id)),
        "can_edit": bool(user and p.owner_id == user.id),
        "videos": [video_json(v, user, db) for v in rows if can_view(v, user, db) and v.status == "ready"],
    }


@router.put("/playlists/{playlist_id}/videos/{video_id}")
def add_to_playlist(
    playlist_id: str, video_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)
):
    p = get_playlist(playlist_id, user, db, owner=True)
    get_video(video_id, user, db)
    if not db.get(PlaylistItem, (p.id, video_id)):
        db.add(PlaylistItem(playlist_id=p.id, video_id=video_id))
        commit_unique(db)
    return {"ok": True}


@router.delete("/playlists/{playlist_id}/videos/{video_id}", status_code=204)
def remove_from_playlist(
    playlist_id: str, video_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)
):
    get_playlist(playlist_id, user, db, owner=True)
    db.execute(
        delete(PlaylistItem).where(PlaylistItem.playlist_id == playlist_id, PlaylistItem.video_id == video_id)
    )
    db.commit()


@router.delete("/playlists/{playlist_id}", status_code=204)
def delete_playlist(playlist_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    p = get_playlist(playlist_id, user, db, owner=True)
    db.delete(p)
    db.commit()


@router.post("/videos/{video_id}/reports", status_code=201)
def report(video_id: str, data: ReportInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    get_video(video_id, user, db)
    r = db.scalar(select(Report).where(Report.video_id == video_id, Report.user_id == user.id))
    if not r:
        db.add(Report(video_id=video_id, user_id=user.id, reason=data.reason))
        commit_unique(db)
    return {"ok": True}


@router.get("/moderation/reports")
def reports(user=Depends(require_moderator), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Report).where(Report.resolved.is_(False)).order_by(Report.created_at).limit(100)
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "reason": r.reason,
                "created_at": r.created_at,
                "reporter": user_json(db.get(User, r.user_id)),
                "video": video_json(db.get(Video, r.video_id), user, db),
            }
            for r in rows
        ]
    }


@router.put("/moderation/videos/{video_id}")
def moderate(video_id: str, data: ModerationInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    if user.role not in ("moderator", "admin"):
        raise HTTPException(403, "Недостаточно прав")
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Видео не найдено")
    v.hidden, v.moderation_reason = data.hidden, data.reason
    for r in db.scalars(select(Report).where(Report.video_id == video_id)):
        r.resolved = True
    db.add(
        Audit(
            actor_id=user.id,
            action="video.hide" if data.hidden else "video.restore",
            target_id=v.id,
            detail=data.reason,
        )
    )
    db.commit()
    return video_json(v, user, db)


@router.get("/admin/users")
def users(q: str = Query("", max_length=32), user=Depends(require_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Требуются права администратора")
    rows = db.scalars(
        select(User)
        .where(User.handle.contains(q.lower(), autoescape=True))
        .order_by(User.created_at)
        .limit(100)
    ).all()
    return {"items": [user_json(u) for u in rows]}


@router.put("/admin/users/{user_id}/role")
def set_role(user_id: str, data: RoleInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Требуются права администратора")
    # Serialize role changes so two administrators cannot demote each other concurrently.
    admins = db.scalars(select(User).where(User.role == "admin").order_by(User.id).with_for_update()).all()
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    if target.role == "admin" and data.role != "admin" and len(admins) <= 1:
        raise HTTPException(409, "Должен остаться хотя бы один администратор")
    target.role = data.role
    db.add(Audit(actor_id=user.id, action="user.role", target_id=target.id, detail=data.role))
    db.commit()
    return user_json(target)
