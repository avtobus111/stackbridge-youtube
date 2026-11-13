import time
from pathlib import Path
from alembic import command
from alembic.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from .db import engine
from .storage import store, bucket
from .seed import seed


def initialize():
    # Readiness polling is bounded. Compose does not start the web/worker before this exits successfully.
    for attempt in range(60):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            s3 = store()
            try:
                s3.head_bucket(Bucket=bucket())
            except ClientError as error:
                if str(error.response["Error"]["Code"]) not in ("404", "NoSuchBucket", "NotFound"):
                    raise
                s3.create_bucket(Bucket=bucket())
            break
        except (ClientError, BotoCoreError, OSError, OperationalError):
            if attempt == 59:
                raise
            time.sleep(2)
    configuration = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    with engine.connect() as lock:
        if engine.dialect.name == "postgresql":
            lock.execute(text("SELECT pg_advisory_lock(70820261113)"))
        try:
            command.upgrade(configuration, "head")
            print(seed())
        finally:
            if engine.dialect.name == "postgresql":
                lock.execute(text("SELECT pg_advisory_unlock(70820261113)"))


if __name__ == "__main__":
    initialize()
