from conftest import register, login, ready_video


def promote(handle, role):
    from backend.db import SessionLocal
    from backend.models import User
    from sqlalchemy import select
    with SessionLocal() as db:
        db.scalar(select(User).where(User.handle == handle)).role = role
        db.commit()


def test_private_discovery_and_grants_revocation(client):
    owner = register(client)
    private = ready_video(client, 'Secret project', 'private')['id']
    public = ready_video(client, 'Public project')['id']
    register(client, 'bob')
    paths = [f'/api/videos/{private}', f'/api/videos/{private}/media', f'/api/videos/{private}/thumbnail', f'/api/videos/{private}/comments']
    for path in paths:
        assert client.get(path).status_code == 404, path
    assert {x['id'] for x in client.get('/api/videos').json()['items']} == {public}
    assert client.get('/api/videos?q=Secret').json()['items'] == []
    assert {x['id'] for x in client.get(f'/api/channels/{owner["handle"]}').json()['videos']} == {public}
    login(client)
    assert client.put(f'/api/videos/{private}/grants', json={'handles': ['bob']}).status_code == 200
    login(client, 'bob')
    assert client.get(f'/api/videos/{private}').status_code == 200
    assert client.get(f'/api/videos/{private}/media', headers={'Range': 'bytes=2-4'}).content == b'234'
    login(client)
    assert client.put(f'/api/videos/{private}/grants', json={'handles': []}).status_code == 200
    login(client, 'bob')
    assert client.get(f'/api/videos/{private}/media').status_code == 404


def test_only_owner_can_edit_and_grant(client):
    register(client)
    video = ready_video(client)['id']
    register(client, 'bob')
    assert client.patch(f'/api/videos/{video}', json={'title': 'Hijack'}).status_code == 403
    assert client.put(f'/api/videos/{video}/grants', json={'handles': ['bob']}).status_code == 403
    assert client.delete(f'/api/videos/{video}').status_code == 403


def test_moderation_hides_public_video_and_is_audited(client):
    register(client)
    vid = ready_video(client)['id']
    register(client, 'bob')
    assert client.post(f'/api/videos/{vid}/reports', json={'reason': 'Needs review'}).status_code == 201
    assert client.get('/api/moderation/reports').status_code == 403
    assert client.put(f'/api/moderation/videos/{vid}', json={'hidden': True, 'reason': 'Rule violation'}).status_code == 403
    promote('bob', 'moderator')
    assert len(client.get('/api/moderation/reports').json()['items']) == 1
    assert client.put(f'/api/moderation/videos/{vid}', json={'hidden': True, 'reason': 'Rule violation'}).status_code == 200
    client.cookies.clear()
    assert client.get(f'/api/videos/{vid}').status_code == 404
    assert client.get('/api/videos').json()['items'] == []
    login(client)
    assert client.get(f'/api/videos/{vid}').json()['hidden'] is True
    from backend.db import SessionLocal
    from backend.models import Audit
    from sqlalchemy import select
    with SessionLocal() as db:
        assert db.scalar(select(Audit)).action == 'video.hide'


def test_role_changes_require_admin_and_last_admin_cannot_remove_self(client):
    user = register(client)
    bob = register(client, 'bob')
    assert client.put(f'/api/admin/users/{user["id"]}/role', json={'role': 'admin'}).status_code == 403
    promote('alice', 'admin')
    login(client)
    assert client.put(f'/api/admin/users/{bob["id"]}/role', json={'role': 'moderator'}).status_code == 200
    assert client.put(f'/api/admin/users/{user["id"]}/role', json={'role': 'user'}).status_code == 409


def test_unknown_grant_handle_is_rejected_atomically(client):
    register(client)
    vid = ready_video(client, visibility='private')['id']
    assert client.put(f'/api/videos/{vid}/grants', json={'handles': ['no_such_account']}).status_code == 422
    assert client.get(f'/api/videos/{vid}/grants').json()['handles'] == []

