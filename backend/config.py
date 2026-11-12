from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'postgresql+psycopg://stackbridge:stackbridge@db/stackbridge'
    s3_endpoint: str = 'http://storage:9000'
    s3_access_key: str = ''
    s3_secret_key: str = ''
    s3_bucket: str = 'videos'
    public_origin: str = 'http://localhost:8000'
    cookie_secure: bool = False
    session_days: int = 7
    auth_rate_limit: int = 20
    max_upload_bytes: int = 536870912
    max_duration_seconds: int = 10800
    ffmpeg: str = 'ffmpeg'
    ffprobe: str = 'ffprobe'
    worker_timeout: int = 600
    worker_lease_seconds: int = 900
    demo_password: str = ''


@lru_cache
def settings():
    return Settings()

