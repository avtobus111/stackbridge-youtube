from conftest import register, login


def test_registration_persists_session_and_revokes_on_logout(client):
    user = register(client)
    assert user['handle'] == 'alice'
    assert user['role'] == 'user'
    assert 'password' not in user and 'password_hash' not in user
    assert client.get('/api/auth/me').json()['user']['id'] == user['id']
    old_cookie = client.cookies.get('session')
    assert client.post('/api/auth/logout').status_code == 204
    client.cookies.set('session', old_cookie)
    assert client.get('/api/auth/me').json()['user'] is None
    login(client)


def test_duplicate_handle_case_insensitive_and_invalid_password(client):
    register(client)
    assert client.post('/api/auth/register', json={'handle': 'ALICE', 'name': 'A', 'password': 'another-password'}).status_code == 409
    assert client.post('/api/auth/login', json={'handle': 'alice', 'password': 'wrong-password'}).status_code == 401


def test_signup_cannot_inject_privileged_role(client):
    r = client.post('/api/auth/register', json={'handle': 'eve', 'name': 'Eve', 'password': 'long-enough-password', 'role': 'admin'})
    assert r.status_code == 422


def test_csrf_and_origin_are_enforced(client):
    register(client)
    csrf = client.headers.pop('X-CSRF-Token')
    assert client.post('/api/auth/logout').status_code == 403
    client.headers['X-CSRF-Token'] = csrf
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/auth/logout').status_code == 204


def test_short_password_and_invalid_handle_rejected(client):
    for data in [{'handle': 'bad/handle', 'password': 'long-password', 'name': 'Bad'}, {'handle': 'valid', 'password': 'short', 'name': 'Name'}]:
        assert client.post('/api/auth/register', json=data).status_code == 422


def test_login_cookie_is_httponly_and_samesite(client):
    r = client.post('/api/auth/register', json={'handle': 'user1', 'name': 'User', 'password': 'long-password'})
    cookie = r.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie
    assert client.get('/healthz').status_code == 200
    assert client.get('/docs').status_code == 200

