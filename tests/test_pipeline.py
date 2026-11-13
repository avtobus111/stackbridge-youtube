import subprocess
import time
from conftest import register, login


def test_complete_real_video_scenario(client, tmp_path):
    register(client)
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=15",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-y",
            str(source),
        ],
        check=True,
        timeout=30,
    )
    r = client.post("/api/videos", json={"title": "From upload to playback", "visibility": "private"})
    assert r.status_code == 201
    vid = r.json()["id"]
    r = client.put(
        f"/api/videos/{vid}/source",
        content=source.read_bytes(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 202, r.text
    assert client.get(f"/api/videos/{vid}").json()["status"] == "queued"
    from backend.worker import process_one

    assert process_one() is True
    detail = client.get(f"/api/videos/{vid}").json()
    assert detail["status"] == "ready", detail
    assert detail["duration"] >= 0.9
    video = client.get(f"/api/videos/{vid}/media")
    assert video.status_code == 200 and b"ftyp" in video.content[:32]
    assert client.get(f"/api/videos/{vid}/thumbnail").content[:2] == b"\xff\xd8"
    assert client.put(f"/api/videos/{vid}/like").json()["likes"] == 1
    assert client.post(f"/api/videos/{vid}/comments", json={"body": "Pipeline works"}).status_code == 201
    assert process_one() is False
    assert client.put(f"/api/videos/{vid}/source", content=b"again").status_code == 409
    register(client, "bob")
    assert client.get(f"/api/videos/{vid}/media").status_code == 404
    login(client)
    assert client.put(f"/api/videos/{vid}/grants", json={"handles": ["bob"]}).status_code == 200
    login(client, "bob")
    assert client.get(f"/api/videos/{vid}/media", headers={"Range": "bytes=0-15"}).status_code == 206


def test_invalid_media_fails_visibly_without_processing_loop(client):
    register(client)
    vid = client.post("/api/videos", json={"title": "Bad input"}).json()["id"]
    assert client.put(f"/api/videos/{vid}/source", content=b"not a video").status_code == 202
    from backend.worker import process_one

    assert process_one() is True
    detail = client.get(f"/api/videos/{vid}").json()
    assert detail["status"] == "failed" and detail["error"]
    assert process_one() is False
    assert client.get(f"/api/videos/{vid}/media").status_code == 409


def test_upload_size_limit_and_empty_file(client, monkeypatch):
    register(client)
    from backend.config import settings

    monkeypatch.setattr(settings(), "max_upload_bytes", 32)
    vid = client.post("/api/videos", json={"title": "Too large"}).json()["id"]
    assert client.put(f"/api/videos/{vid}/source", content=b"x" * 33).status_code == 413
    assert client.put(f"/api/videos/{vid}/source", content=b"").status_code == 422


def test_expired_worker_lease_is_recovered(client):
    register(client)
    vid = client.post("/api/videos", json={"title": "Interrupted job"}).json()["id"]
    assert client.put(f"/api/videos/{vid}/source", content=b"broken").status_code == 202
    from backend.db import SessionLocal
    from backend.models import Video
    from backend.worker import process_one

    with SessionLocal() as db:
        v = db.get(Video, vid)
        v.status, v.lease_at, v.attempts = "processing", time.time() - 2000, 1
        db.commit()
    assert process_one() is True
    assert client.get(f"/api/videos/{vid}").json()["status"] == "failed"
