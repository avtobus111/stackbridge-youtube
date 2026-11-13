"""Idempotent, offline-after-install demo data. Assets are bundled in the repository."""

import json
import time
import uuid
from pathlib import Path
from sqlalchemy import select, func
from .config import settings
from .db import SessionLocal
from .models import User, Video, Playlist, PlaylistItem, Comment, Subscription
from .security import hash_password
from .storage import store, bucket

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "demo"
CHANNELS = [
    ("north", "Северный свет", "#547867", "Небольшие истории о больших пространствах."),
    ("city", "Город и люди", "#9b644e", "Архитектура, путешествия и повседневная жизнь."),
    ("tech", "Простая техника", "#456b96", "Технологии крупным планом."),
    ("stories", "Тихие истории", "#7c658c", "Остановиться и посмотреть вокруг."),
    ("sound", "Звук вокруг", "#af6549", "Музыка, инструменты и вдохновение."),
    ("taste", "Вкусный кадр", "#72814a", "Еда и маленькие повседневные ритуалы."),
]
VIDEOS = [
    ("Один день в горах — визуальный этюд", "north", "Природа"),
    ("Город после заката: свет, улицы и движение", "city", "Путешествия"),
    ("Внутри технологий: красота электронных схем", "tech", "Технологии"),
    ("Когда город засыпает. Небо без спешки", "stories", "Вдохновение"),
    ("Навстречу тишине: горы под звёздами", "north", "Природа"),
    ("Весна в деталях — маленькая пауза", "stories", "Природа"),
    ("Линии города: взгляд на архитектуру", "city", "Архитектура"),
    ("Земля с другого ракурса", "tech", "Технологии"),
    ("Настроение акустики: гитара крупным планом", "sound", "Музыка"),
    ("Цвет на кухне: вдохновение для ужина", "taste", "Кулинария"),
    ("Утро начинается с кофе", "taste", "Кулинария"),
    ("Рабочее место, которое вдохновляет", "tech", "Вдохновение"),
]


def deterministic_id(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "stackbridge-demo/" + value))


def seed():
    password = settings().demo_password
    if len(password) < 10:
        raise RuntimeError("DEMO_PASSWORD must be set to at least 10 characters before seeding")
    if not (ASSETS / "01.mp4").is_file():
        raise RuntimeError("Bundled demo assets are missing")
    now = time.time()
    s3 = store()
    with SessionLocal() as db:
        users = {}
        accounts = CHANNELS + [
            ("viewer", "Зритель", "#065fd4", ""),
            ("creator", "Мой канал", "#a75d74", ""),
            ("moderator", "Модератор", "#557a68", ""),
            ("admin", "Администратор", "#606060", ""),
        ]
        for handle, name, color, description in accounts:
            user = db.scalar(select(User).where(User.handle == handle))
            if not user:
                user = User(
                    id=deterministic_id("user/" + handle),
                    handle=handle,
                    name=name,
                    color=color,
                    description=description,
                    password_hash=hash_password(password),
                    role="admin" if handle == "admin" else "moderator" if handle == "moderator" else "user",
                )
                db.add(user)
                db.flush()
            # Existing accounts are never promoted or have their password overwritten.
            users[handle] = user
        for index, (title, owner, category) in enumerate(VIDEOS, 1):
            video_id = deterministic_id("video/" + str(index))
            if db.get(Video, video_id):
                continue
            source, media, thumbnail = f"{video_id}/source", f"{video_id}/video.mp4", f"{video_id}/thumb.jpg"
            path = ASSETS / f"{index:02d}.mp4"
            s3.upload_file(str(path), bucket(), source, ExtraArgs={"ContentType": "video/mp4"})
            s3.upload_file(str(path), bucket(), media, ExtraArgs={"ContentType": "video/mp4"})
            s3.upload_file(
                str(ASSETS / f"{index:02d}.jpg"), bucket(), thumbnail, ExtraArgs={"ContentType": "image/jpeg"}
            )
            db.add(
                Video(
                    id=video_id,
                    owner_id=users[owner].id,
                    title=title,
                    category=category,
                    description="Демонстрационный визуальный этюд. Плавное движение фотографии и синтезированный звук.\n\nИзображение: Unsplash. Этот короткий ролик создан для проверки приложения; он не является записью события или полноценным уроком.",
                    source_key=source,
                    media_key=media,
                    thumbnail_key=thumbnail,
                    status="ready",
                    duration=8,
                    size=path.stat().st_size,
                    created_at=now - (index - 1) * 13700,
                )
            )
            db.flush()
            db.add(
                Comment(
                    id=deterministic_id("comment/" + str(index)),
                    video_id=video_id,
                    user_id=users["viewer"].id,
                    body=[
                        "Красивый кадр. Спасибо за небольшую паузу!",
                        "Хочется рассмотреть каждую деталь.",
                        "Отличное настроение для начала дня.",
                    ][index % 3],
                    created_at=now - index * 4000,
                )
            )
        for handle, _, _, _ in CHANNELS:
            p_id = deterministic_id("playlist/" + handle)
            if not db.get(Playlist, p_id):
                p = Playlist(
                    id=p_id, owner_id=users[handle].id, title="Избранные истории", visibility="public"
                )
                db.add(p)
                db.flush()
                for index, (_, owner, _) in enumerate(VIDEOS, 1):
                    if owner == handle:
                        db.add(
                            PlaylistItem(playlist_id=p_id, video_id=deterministic_id("video/" + str(index)))
                        )
            if not db.get(Subscription, (users["viewer"].id, users[handle].id)):
                db.add(Subscription(user_id=users["viewer"].id, channel_id=users[handle].id))
        db.commit()
        return {
            "users": db.scalar(select(func.count()).select_from(User)),
            "videos": db.scalar(select(func.count()).select_from(Video)),
        }


if __name__ == "__main__":
    print(json.dumps(seed(), ensure_ascii=False))
