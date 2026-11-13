import pytest
from conftest import register, login, ready_video
from test_access import promote


@pytest.mark.parametrize("role", ["moderator", "admin"])
def test_staff_need_owner_permission_for_private_video(client, role):
    owner = register(client)
    vid = ready_video(client, "Owner permission only", "private")["id"]
    register(client, "staff")
    promote("staff", role)
    for suffix in ["", "/media", "/thumbnail", "/comments"]:
        assert client.get(f"/api/videos/{vid}{suffix}").status_code == 404
    assert client.get(f"/api/videos/{vid}/media", headers={"Range": "bytes=0-3"}).status_code == 404
    assert client.get("/api/videos?q=Owner").json()["items"] == []
    assert client.get(f"/api/channels/{owner['handle']}").json()["videos"] == []
    login(client)
    client.put(f"/api/videos/{vid}/grants", json={"handles": ["staff"]})
    login(client, "staff")
    assert client.get(f"/api/videos/{vid}/media").content == b"0123456789"


def test_moderation_report_does_not_reveal_private_metadata(client):
    register(client)
    vid = ready_video(client, "Private title must stay private", "private")["id"]
    register(client, "viewer")
    login(client)
    client.put(f"/api/videos/{vid}/grants", json={"handles": ["viewer"]})
    login(client, "viewer")
    client.post(f"/api/videos/{vid}/reports", json={"reason": "Please review access policy"})
    register(client, "staff")
    promote("staff", "moderator")
    report = client.get("/api/moderation/reports").json()["items"][0]
    assert report["video"]["id"] == vid
    assert report["video"]["can_view"] is False
    assert "Private title must stay private" not in str(report)
    response = client.put(
        f"/api/moderation/videos/{vid}", json={"hidden": True, "reason": "Reported violation"}
    )
    assert response.status_code == 200
    assert "Private title must stay private" not in response.text
    assert client.get(f"/api/videos/{vid}/media").status_code == 404
