from conftest import register


def test_seed_is_idempotent_and_has_playable_demo(client,monkeypatch):
    import importlib.util
    assert importlib.util.find_spec('backend.seed'),'Demo seed is not implemented yet'
    from backend.config import settings
    monkeypatch.setattr(settings(),'demo_password','test-seed-password')
    from backend.seed import seed
    first=seed()
    second=seed()
    assert first['videos'] == second['videos'] == 12
    rows=client.get('/api/videos').json()['items']
    assert len(rows) >= 10
    assert client.get(rows[0]['media']).status_code == 200
    from backend.db import SessionLocal
    from backend.models import User
    from sqlalchemy import select
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.handle == 'admin')).role == 'admin'
