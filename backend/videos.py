import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select, func, exists, delete
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Video, Grant, Like, Comment, Subscription, Playlist, PlaylistItem
from .schemas import VideoInput, GrantInput, ChannelInput
from .security import current_user, require_csrf, require_user, user_json
from .storage import store, bucket

router = APIRouter(prefix='/api', tags=['Videos and channels'])


def allowed_condition(user):
    if user and user.role in ('moderator', 'admin'):
        return True
    public = and_(Video.visibility == 'public', Video.status == 'ready', Video.hidden.is_(False))
    if not user:
        return public
    granted = and_(Video.status == 'ready', Video.hidden.is_(False),
                   exists(select(Grant.video_id).where(Grant.video_id == Video.id, Grant.user_id == user.id)))
    return or_(public, Video.owner_id == user.id, granted)


def can_view(video, user, db):
    if user and (video.owner_id == user.id or user.role in ('moderator', 'admin')):
        return True
    if video.hidden or video.status != 'ready':
        return False
    return video.visibility == 'public' or bool(user and db.get(Grant, (video.id, user.id)))


def get_video(video_id, user, db):
    video = db.get(Video, video_id)
    if not video or not can_view(video, user, db):
        raise HTTPException(404, 'Видео недоступно')
    return video


def own_video(video_id, user, db):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, 'Видео не найдено')
    if video.owner_id != user.id:
        raise HTTPException(403, 'Изменять видео может только владелец')
    return video


def count(db, model, *conditions):
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def video_json(video, user, db):
    channel = db.get(User, video.owner_id)
    editable = bool(user and video.owner_id == user.id)
    result = {field: getattr(video, field) for field in ('id','title','description','category','visibility','status','hidden','duration','views','created_at','moderation_reason')}
    result.update(channel=user_json(channel), likes=count(db, Like, Like.video_id == video.id),
                  comments=count(db, Comment, Comment.video_id == video.id),
                  liked=bool(user and db.get(Like, (video.id, user.id))), can_edit=editable,
                  thumbnail=f'/api/videos/{video.id}/thumbnail' if video.thumbnail_key else None,
                  media=f'/api/videos/{video.id}/media' if video.status == 'ready' else None,
                  error=video.error if editable or (user and user.role in ('admin','moderator')) else '')
    return result


@router.get('/videos')
def list_videos(q: str = Query(default='', max_length=140), category: str = '', feed: str = '',
                offset: int = Query(0, ge=0, le=100000), limit: int = Query(24, ge=1, le=50),
                user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(Video).where(Video.status == 'ready', allowed_condition(user))
    if q.strip():
        # Escape wildcard characters so the UI really searches by entered title.
        escaped = q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query = query.where(Video.title.ilike(f'%{escaped}%', escape='\\'))
    if category:
        query = query.where(Video.category == category)
    if feed == 'subscriptions':
        if not user:
            raise HTTPException(401, 'Войдите, чтобы увидеть подписки')
        query = query.where(Video.owner_id.in_(select(Subscription.channel_id).where(Subscription.user_id == user.id)))
    if feed == 'liked':
        if not user:
            raise HTTPException(401, 'Войдите, чтобы увидеть понравившиеся видео')
        query = query.where(Video.id.in_(select(Like.video_id).where(Like.user_id == user.id)))
    rows = db.scalars(query.order_by(Video.created_at.desc()).offset(offset).limit(limit + 1)).all()
    return {'items': [video_json(x, user, db) for x in rows[:limit]], 'has_more': len(rows) > limit}


@router.post('/videos', status_code=201)
def create_video(data: VideoInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    if count(db, Video, Video.owner_id == user.id, Video.status.in_(['uploading','receiving','queued','processing'])) >= 10:
        raise HTTPException(429, 'Дождитесь обработки предыдущих видео')
    video = Video(owner_id=user.id, **data.model_dump())
    db.add(video)
    db.commit()
    return video_json(video, user, db)


@router.get('/studio')
def studio(user=Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Video).where(Video.owner_id == user.id).order_by(Video.created_at.desc()).limit(100)).all()
    return {'items': [video_json(x, user, db) for x in rows]}


@router.get('/videos/{video_id}')
def detail(video_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return video_json(get_video(video_id, user, db), user, db)


@router.patch('/videos/{video_id}')
def edit(video_id: str, data: VideoInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    video = own_video(video_id, user, db)
    for key, value in data.model_dump().items():
        setattr(video, key, value)
    video.updated_at = time.time()
    db.commit()
    return video_json(video, user, db)


@router.delete('/videos/{video_id}', status_code=204)
def remove(video_id: str, user=Depends(require_csrf), db: Session = Depends(get_db)):
    video = own_video(video_id, user, db)
    if video.status in ('receiving', 'processing'):
        raise HTTPException(409, 'Дождитесь окончания загрузки или обработки')
    keys = [x for x in (video.source_key, video.media_key, video.thumbnail_key) if x]
    if keys:
        store().delete_objects(Bucket=bucket(), Delete={'Objects': [{'Key': x} for x in keys]})
    db.delete(video)
    db.commit()


@router.get('/videos/{video_id}/grants')
def grants(video_id: str, user=Depends(require_user), db: Session = Depends(get_db)):
    own_video(video_id, user, db)
    handles = db.scalars(select(User.handle).join(Grant, Grant.user_id == User.id).where(Grant.video_id == video_id)).all()
    return {'handles': handles}


@router.put('/videos/{video_id}/grants')
def set_grants(video_id: str, data: GrantInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    own_video(video_id, user, db)
    users = db.scalars(select(User).where(User.handle.in_(data.handles))).all() if data.handles else []
    if len(users) != len(data.handles):
        raise HTTPException(422, 'Не все указанные пользователи найдены')
    db.execute(delete(Grant).where(Grant.video_id == video_id))
    db.add_all(Grant(video_id=video_id, user_id=u.id) for u in users if u.id != user.id)
    db.commit()
    return {'handles': [u.handle for u in users if u.id != user.id]}


@router.get('/channels/{handle}')
def channel_detail(handle: str, user=Depends(current_user), db: Session = Depends(get_db)):
    channel = db.scalar(select(User).where(User.handle == handle.lower()))
    if not channel:
        raise HTTPException(404, 'Канал не найден')
    videos = db.scalars(select(Video).where(Video.owner_id == channel.id, Video.status == 'ready', allowed_condition(user)).order_by(Video.created_at.desc()).limit(100)).all()
    playlists = db.scalars(select(Playlist).where(Playlist.owner_id == channel.id,
                    or_(Playlist.visibility == 'public', Playlist.owner_id == (user.id if user else ''))).order_by(Playlist.created_at.desc())).all()
    return {'channel': user_json(channel), 'videos': [video_json(x,user,db) for x in videos],
            'subscribers': count(db, Subscription, Subscription.channel_id == channel.id),
            'subscribed': bool(user and db.get(Subscription,(user.id,channel.id))),
            'playlists': [{'id':p.id,'title':p.title,'visibility':p.visibility} for p in playlists]}


@router.patch('/channel')
def edit_channel(data: ChannelInput, user=Depends(require_csrf), db: Session = Depends(get_db)):
    user.name, user.description = data.name, data.description
    db.commit()
    return user_json(user)

