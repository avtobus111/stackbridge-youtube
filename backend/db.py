from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings


class Base(DeclarativeBase):
    pass


url = settings().database_url
options = {'connect_args': {'check_same_thread': False}, 'poolclass': StaticPool} if url.startswith('sqlite') else {'pool_pre_ping': True}
engine = create_engine(url, **options)
if url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db

