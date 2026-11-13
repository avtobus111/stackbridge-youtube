"""Verify signed S3 access and reject unsigned reads against the running real store.

Run inside the web container with:
docker compose exec -T web python - < scripts/check_storage.py
"""

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import select

from backend.config import settings
from backend.db import SessionLocal
from backend.models import Video
from backend.storage import bucket, store


def main():
    with SessionLocal() as db:
        key = db.scalar(select(Video.media_key).where(Video.status == "ready").limit(1))
    if not key:
        raise RuntimeError("A processed video is required to check real object access")
    store().head_object(Bucket=bucket(), Key=key)
    unsigned = boto3.client(
        "s3",
        endpoint_url=settings().s3_endpoint,
        aws_access_key_id="anonymous",
        aws_secret_access_key="anonymous",
        region_name="us-east-1",
        config=Config(
            signature_version=UNSIGNED, connect_timeout=5, read_timeout=10, s3={"addressing_style": "path"}
        ),
    )
    try:
        response = unsigned.get_object(Bucket=bucket(), Key=key)
    except ClientError as error:
        assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 403, error.response["Error"]["Code"]
    else:
        response["Body"].close()
        raise AssertionError("Unsigned object access must be denied")
    print("PASS: signed S3 access works; unsigned object read returns 403")


if __name__ == "__main__":
    main()
