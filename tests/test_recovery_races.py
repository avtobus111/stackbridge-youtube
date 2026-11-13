from botocore.exceptions import ClientError
from conftest import register


def test_stale_upload_cannot_replace_newer_completed_attempt(client, monkeypatch):
    register(client)
    vid = client.post("/api/videos", json={"title": "Interleaved uploads"}).json()["id"]
    from backend import media
    from backend.db import SessionLocal
    from backend.models import Video
    from backend.storage import store, bucket

    async def finish_storage_then_complete_new_attempt(function, *args):
        function(*args)  # Actual S3 I/O for the old attempt; schedule newer completion before old DB commit.
        store().put_object(Bucket=bucket(), Key=f"{vid}/new-source", Body=b"new source")
        with SessionLocal() as db:
            video = db.get(Video, vid)
            video.status, video.lease_at, video.source_key = "ready", 999, f"{vid}/new-source"
            db.commit()

    monkeypatch.setattr(media, "run_in_threadpool", finish_storage_then_complete_new_attempt)
    response = client.put(f"/api/videos/{vid}/source", content=b"old source")
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        video = db.get(Video, vid)
        assert video.status == "ready" and video.source_key == f"{vid}/new-source" and video.lease_at == 999


def test_stale_upload_failure_does_not_reset_new_receiving_attempt(client, monkeypatch):
    register(client)
    vid = client.post("/api/videos", json={"title": "Interleaved upload failure"}).json()["id"]
    from backend import media
    from backend.db import SessionLocal
    from backend.models import Video

    async def fail_after_new_attempt_claims(function, *args):
        with SessionLocal() as db:
            video = db.get(Video, vid)
            video.status, video.lease_at = "receiving", 999
            db.commit()
        raise ClientError(
            {"Error": {"Code": "InternalError", "Message": "Scheduled storage failure"}}, "PutObject"
        )

    monkeypatch.setattr(media, "run_in_threadpool", fail_after_new_attempt_claims)
    assert client.put(f"/api/videos/{vid}/source", content=b"old source").status_code == 503
    with SessionLocal() as db:
        assert db.get(Video, vid).status == "receiving"


def test_stale_worker_cannot_overwrite_new_ready_objects(client, monkeypatch):
    register(client)
    vid = client.post("/api/videos", json={"title": "Interleaved workers"}).json()["id"]
    assert client.put(f"/api/videos/{vid}/source", content=b"source").status_code == 202
    from backend import worker
    from backend.db import SessionLocal
    from backend.models import Video
    from backend.storage import store, bucket

    def delayed_old_transcode(source, media, thumbnail):
        media.write_bytes(b"old processed video")
        thumbnail.write_bytes(b"old thumbnail")
        # Another worker has claimed and published the newer source while the first was suspended.
        store().put_object(Bucket=bucket(), Key=f"{vid}/video.mp4", Body=b"new processed video")
        store().put_object(Bucket=bucket(), Key=f"{vid}/thumb.jpg", Body=b"new thumbnail")
        with SessionLocal() as db:
            video = db.get(Video, vid)
            video.status, video.lease_at, video.media_key, video.thumbnail_key = (
                "ready",
                999,
                f"{vid}/video.mp4",
                f"{vid}/thumb.jpg",
            )
            db.commit()
        return 1.0

    monkeypatch.setattr(worker, "transcode", delayed_old_transcode)
    assert worker.process_one() is True
    assert client.get(f"/api/videos/{vid}/media").content == b"new processed video"
    assert client.get(f"/api/videos/{vid}/thumbnail").content == b"new thumbnail"
    with SessionLocal() as db:
        assert db.get(Video, vid).lease_at == 999
