"""End-to-end API smoke against a running real PostgreSQL/S3/worker stack (stdlib only)."""

import http.cookiejar
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.csrf = ""

    def call(self, path, method="GET", data=None, raw=None, headers=None, expected=200):
        request_headers = {"Origin": self.base, **(headers or {})}
        if self.csrf:
            request_headers["X-CSRF-Token"] = self.csrf
        if data is not None:
            raw = json.dumps(data).encode()
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=raw, method=method, headers=request_headers)
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        body = response.read()
        assert response.status == expected, (
            f"{method} {path}: expected {expected}, got {response.status}: {body[:250]!r}"
        )
        if not body:
            return None
        if "application/json" in response.headers.get("Content-Type", ""):
            result = json.loads(body)
            if "csrf_token" in result:
                self.csrf = result["csrf_token"]
            return result
        return body

    def signup(self, prefix):
        handle = prefix + secrets.token_hex(4)
        self.call(
            "/api/auth/register",
            "POST",
            data={"handle": handle, "name": "Smoke test", "password": secrets.token_urlsafe(18)},
            expected=201,
        )
        return handle


def main(base):
    owner, viewer, anonymous = Client(base), Client(base), Client(base)
    owner.signup("smoke_")
    handle = viewer.signup("viewer_")
    assert owner.call("/healthz")["ready"] is True
    v = owner.call(
        "/api/videos",
        "POST",
        data={"title": "Smoke upload → playback", "visibility": "private"},
        expected=201,
    )
    vid = v["id"]
    sample = Path(__file__).resolve().parent.parent / "assets/demo/01.mp4"
    owner.call(
        f"/api/videos/{vid}/source",
        "PUT",
        raw=sample.read_bytes(),
        headers={"Content-Type": "application/octet-stream"},
        expected=202,
    )
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        video = owner.call(f"/api/videos/{vid}")
        if video["status"] in ("ready", "failed"):
            break
        time.sleep(1)
    assert video["status"] == "ready", video
    media = owner.call(f"/api/videos/{vid}/media")
    assert b"ftyp" in media[:32]
    assert owner.call(f"/api/videos/{vid}/thumbnail")[:2] == b"\xff\xd8"
    assert len(owner.call(f"/api/videos/{vid}/media", headers={"Range": "bytes=0-15"}, expected=206)) == 16
    viewer.call(f"/api/videos/{vid}/media", expected=404)
    anonymous.call(f"/api/videos/{vid}/thumbnail", expected=404)
    owner.call(f"/api/videos/{vid}/grants", "PUT", data={"handles": [handle]})
    viewer.call(f"/api/videos/{vid}/media", headers={"Range": "bytes=-16"}, expected=206)
    assert viewer.call(f"/api/videos/{vid}/like", "PUT")["likes"] == 1
    viewer.call(
        f"/api/videos/{vid}/comments",
        "POST",
        data={"body": "Real PostgreSQL + S3 + worker verified"},
        expected=201,
    )
    assert owner.call(f"/api/videos/{vid}/comments")["items"][0]["body"].startswith("Real PostgreSQL")
    playlist = owner.call("/api/playlists", "POST", data={"title": "Smoke playlist"}, expected=201)
    owner.call(f"/api/playlists/{playlist['id']}/videos/{vid}", "PUT")
    assert len(viewer.call(f"/api/playlists/{playlist['id']}")["videos"]) == 1
    owner.call(f"/api/videos/{vid}/grants", "PUT", data={"handles": []})
    viewer.call(f"/api/videos/{vid}/media", expected=404)
    assert viewer.call(f"/api/playlists/{playlist['id']}")["videos"] == []
    owner.call(f"/api/playlists/{playlist['id']}", "DELETE", expected=204)
    owner.call(f"/api/videos/{vid}", "DELETE", expected=204)
    owner.call("/api/auth/logout", "POST", expected=204)
    print(
        "PASS: real-stack upload, processing, playback/ranges, private grants/revocation, likes/comments, playlist filtering and cleanup"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000")
