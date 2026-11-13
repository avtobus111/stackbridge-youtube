import json
import logging
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select, or_, and_, update
from .config import settings
from .db import SessionLocal
from .models import Video
from .storage import store, bucket, discard

log = logging.getLogger("stackbridge.worker")


class InvalidMedia(Exception):
    pass


def transcode(source: Path, media: Path, thumbnail: Path) -> float:
    s = settings()
    try:
        result = subprocess.run(
            [
                s.ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(source),
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        info = json.loads(result.stdout)
        videos = [
            x
            for x in info.get("streams", [])
            if x.get("codec_type") == "video" and not x.get("disposition", {}).get("attached_pic")
        ]
        duration = float(info.get("format", {}).get("duration", 0))
        if not videos or not 0 < duration <= s.max_duration_seconds:
            raise InvalidMedia("Нет видеодорожки или превышена допустимая длительность")
        if int(videos[0].get("width", 0)) * int(videos[0].get("height", 0)) > 7680 * 4320:
            raise InvalidMedia("Разрешение видео слишком большое")
        subprocess.run(
            [
                s.ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-sn",
                "-dn",
                "-vf",
                "scale=w='min(1280,iw)':h=-2,setsar=1",
                "-c:v",
                "libx264",
                "-threads",
                "2",
                "-preset",
                "veryfast",
                "-crf",
                "24",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-y",
                str(media),
            ],
            capture_output=True,
            check=True,
            timeout=s.worker_timeout,
        )
        subprocess.run(
            [
                s.ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-ss",
                str(min(duration / 3, 2)),
                "-i",
                str(media),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                "-y",
                str(thumbnail),
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        return duration
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
        raise InvalidMedia(
            "Не удалось обработать файл. Загрузите корректное видео MP4, WebM или MOV"
        ) from error


def process_one() -> bool:
    now = time.time()
    s = settings()
    with SessionLocal() as db:
        db.execute(
            update(Video)
            .where(Video.status == "receiving", Video.updated_at < now - s.worker_lease_seconds)
            .values(status="failed", error="Загрузка прервана. Загрузите файл повторно")
        )
        candidate = db.scalar(
            select(Video)
            .where(
                or_(
                    and_(Video.status == "queued", Video.lease_at <= now),
                    and_(Video.status == "processing", Video.lease_at < now - s.worker_lease_seconds),
                )
            )
            .order_by(Video.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not candidate:
            db.commit()
            return False
        candidate.status, candidate.lease_at = "processing", now
        candidate.attempts += 1
        candidate.error = ""
        video_id, source_key, attempt = candidate.id, candidate.source_key, candidate.attempts
        db.commit()
    processed_prefix = f"{video_id}/processed/{uuid.uuid4()}"
    media_key, thumbnail_key = f"{processed_prefix}/video.mp4", f"{processed_prefix}/thumb.jpg"
    try:
        if attempt > 3:
            raise InvalidMedia("Обработка прерывалась несколько раз. Загрузите видео повторно")
        with tempfile.TemporaryDirectory(prefix="stackbridge-worker-") as directory:
            folder = Path(directory)
            source, media, thumb = folder / "source", folder / "video.mp4", folder / "thumb.jpg"
            s3 = store()
            s3.download_file(bucket(), source_key, str(source))
            duration = transcode(source, media, thumb)
            s3.upload_file(str(media), bucket(), media_key, ExtraArgs={"ContentType": "video/mp4"})
            s3.upload_file(str(thumb), bucket(), thumbnail_key, ExtraArgs={"ContentType": "image/jpeg"})
            with SessionLocal() as db:
                published = db.execute(
                    update(Video)
                    .where(Video.id == video_id, Video.status == "processing", Video.lease_at == now)
                    .values(
                        status="ready",
                        media_key=media_key,
                        thumbnail_key=thumbnail_key,
                        duration=duration,
                        error="",
                        updated_at=time.time(),
                    )
                )
                db.commit()
            if published.rowcount != 1:
                discard([media_key, thumbnail_key])
        log.info("Processed video %s", video_id)
    except (InvalidMedia, ClientError, BotoCoreError, OSError) as error:
        discard([media_key, thumbnail_key])
        transient = not isinstance(error, InvalidMedia) and attempt < 3
        message = (
            str(error)
            if isinstance(error, InvalidMedia)
            else "Хранилище или обработчик недоступны. Повторите загрузку"
        )
        log.warning("Video %s processing failed (%s)", video_id, type(error).__name__)
        with SessionLocal() as db:
            db.execute(
                update(Video)
                .where(Video.id == video_id, Video.status == "processing", Video.lease_at == now)
                .values(
                    status="queued" if transient else "failed",
                    error=message[:300],
                    lease_at=time.time() + attempt * 10 if transient else 0,
                    updated_at=time.time(),
                )
            )
            db.commit()
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        try:
            if not process_one():
                time.sleep(2)
        except Exception:
            log.exception("Worker loop failed; retrying")
            time.sleep(5)


if __name__ == "__main__":
    main()
