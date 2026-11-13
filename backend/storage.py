import boto3
import logging
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
from .config import settings


def store():
    s = settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint or None,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3},
            s3={"addressing_style": "path"},
        ),
    )


def bucket():
    return settings().s3_bucket


def discard(keys):
    keys = [key for key in keys if key]
    if not keys:
        return
    try:
        store().delete_objects(Bucket=bucket(), Delete={"Objects": [{"Key": key} for key in keys]})
    except (ClientError, BotoCoreError):
        logging.getLogger("stackbridge.storage").warning("Unpublished object cleanup will need retry")
