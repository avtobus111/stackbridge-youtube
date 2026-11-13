from conftest import register, login, ready_video


def test_likes_comments_and_subscriptions(client):
    owner = register(client)
    vid = ready_video(client)["id"]
    register(client, "bob")
    for _ in range(2):
        assert client.put(f"/api/videos/{vid}/like").status_code == 200
    assert client.get(f"/api/videos/{vid}").json()["likes"] == 1
    assert client.post(f"/api/videos/{vid}/comments", json={"body": "Good video!"}).status_code == 201
    assert client.get(f"/api/videos/{vid}/comments").json()["items"][0]["body"] == "Good video!"
    assert client.post(f"/api/videos/{vid}/comments", json={"body": "   "}).status_code == 422
    for _ in range(2):
        assert client.put(f"/api/channels/{owner['handle']}/subscription").status_code == 200
    assert len(client.get("/api/videos?feed=subscriptions").json()["items"]) == 1
    assert client.get(f"/api/channels/{owner['handle']}").json()["subscribers"] == 1
    assert client.delete(f"/api/videos/{vid}/like").status_code == 200
    assert client.get(f"/api/videos/{vid}").json()["likes"] == 0


def test_playlists_never_expose_ungranted_private_videos(client):
    register(client)
    vid = ready_video(client, visibility="private")["id"]
    public = ready_video(client)["id"]
    p = client.post("/api/playlists", json={"title": "My list"}).json()["id"]
    for item in [vid, public]:
        assert client.put(f"/api/playlists/{p}/videos/{item}").status_code == 200
    register(client, "bob")
    detail = client.get(f"/api/playlists/{p}").json()
    assert [x["id"] for x in detail["videos"]] == [public]
    assert client.put(f"/api/playlists/{p}/videos/{public}").status_code == 403


def test_private_playlist_hidden_and_comment_ownership(client):
    register(client)
    vid = ready_video(client)["id"]
    comment = client.post(f"/api/videos/{vid}/comments", json={"body": "Hello"}).json()["id"]
    p = client.post("/api/playlists", json={"title": "Secret list", "visibility": "private"}).json()["id"]
    register(client, "bob")
    assert client.get(f"/api/playlists/{p}").status_code == 404
    assert client.delete(f"/api/comments/{comment}").status_code == 403
    login(client)
    assert client.delete(f"/api/comments/{comment}").status_code == 204


def test_unauthenticated_mutations_rejected(client):
    assert client.post("/api/videos", json={"title": "Anonymous"}).status_code == 401
    assert client.post("/api/playlists", json={"title": "Anonymous"}).status_code == 401
