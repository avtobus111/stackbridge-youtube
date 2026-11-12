import importlib.util
import os

import pytest

os.environ['DATABASE_URL'] = os.environ.get('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')
os.environ['S3_ENDPOINT'] = ''
os.environ['S3_ACCESS_KEY'] = 'testing'
os.environ['S3_SECRET_KEY'] = 'testing'
os.environ['S3_BUCKET'] = 'stackbridge-tests'
os.environ['AUTH_RATE_LIMIT'] = '100'


@pytest.fixture
def client():
    assert importlib.util.find_spec('backend.main'), 'The application API has not been implemented yet'
    from fastapi.testclient import TestClient
    from moto import mock_aws
    from backend.main import create_app
    from backend.db import Base, engine
    from backend.storage import store

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with mock_aws():
        store().create_bucket(Bucket=os.environ['S3_BUCKET'])
        with TestClient(create_app()) as c:
            yield c
    Base.metadata.drop_all(engine)


def register(client, handle='alice', password='correct horse battery'):
    r = client.post('/api/auth/register', json={'handle': handle, 'password': password, 'name': handle.title()})
    assert r.status_code == 201, r.text
    client.headers['X-CSRF-Token'] = r.json()['csrf_token']
    return r.json()['user']


def login(client, handle='alice', password='correct horse battery'):
    client.cookies.clear()
    r = client.post('/api/auth/login', json={'handle': handle, 'password': password})
    assert r.status_code == 200, r.text
    client.headers['X-CSRF-Token'] = r.json()['csrf_token']
    return r.json()['user']


def ready_video(client, title='A real video', visibility='public'):
    r = client.post('/api/videos', json={'title': title, 'visibility': visibility})
    assert r.status_code == 201, r.text
    from backend.db import SessionLocal
    from backend.models import Video
    from backend.storage import store, bucket
    vid = r.json()['id']
    with SessionLocal() as db:
        video = db.get(Video, vid)
        video.status = 'ready'
        video.media_key = f'{vid}/video.mp4'
        video.thumbnail_key = f'{vid}/thumb.jpg'
        video.duration = 3.5
        db.commit()
    store().put_object(Bucket=bucket(), Key=f'{vid}/video.mp4', Body=b'0123456789', ContentType='video/mp4')
    store().put_object(Bucket=bucket(), Key=f'{vid}/thumb.jpg', Body=b'jpeg', ContentType='image/jpeg')
    return r.json()


