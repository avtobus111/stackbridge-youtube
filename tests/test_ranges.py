import pytest
from conftest import register, ready_video


@pytest.mark.parametrize(
    "header,expected",
    [("bytes=0-3", b"0123"), ("bytes=7-", b"789"), ("bytes=-4", b"6789"), ("bytes=0-999", b"0123456789")],
)
def test_range_requests(client, header, expected):
    register(client)
    vid = ready_video(client)["id"]
    r = client.get(f"/api/videos/{vid}/media", headers={"Range": header})
    assert r.status_code == 206
    assert r.content == expected
    assert int(r.headers["content-length"]) == len(expected)
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "header", ["bytes=10-", "bytes=-0", "bytes=4-2", "bytes=0-1,3-4", "garbage", "bytes=abc-def"]
)
def test_invalid_ranges(client, header):
    register(client)
    vid = ready_video(client)["id"]
    r = client.get(f"/api/videos/{vid}/media", headers={"Range": header})
    assert r.status_code == 416
    assert r.headers["content-range"] == "bytes */10"


def test_full_video_and_thumbnail(client):
    register(client)
    vid = ready_video(client)["id"]
    r = client.get(f"/api/videos/{vid}/media")
    assert r.status_code == 200 and r.content == b"0123456789"
    assert r.headers["content-type"] == "video/mp4"
    assert client.get(f"/api/videos/{vid}/thumbnail").content == b"jpeg"
