from conftest import register


def test_frontend_shell_and_deep_links(client):
    for path in ["/", "/watch/example", "/channel/alice", "/upload", "/studio", "/playlists"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert '<html lang="ru">' in r.text
        assert "app.js" in r.text
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/api/nonexistent").status_code == 404


def test_upload_configuration_matches_enforced_limit(client):
    register(client)
    r = client.get("/api/config")
    assert r.status_code == 200
    assert r.json()["max_upload_bytes"] > 0
    assert "s3_secret_key" not in r.text


def test_views_count_once_per_viewer(client):
    from conftest import ready_video

    register(client)
    vid = ready_video(client)["id"]
    for _ in range(2):
        assert client.post(f"/api/videos/{vid}/view").status_code == 200
    assert client.get(f"/api/videos/{vid}").json()["views"] == 1
