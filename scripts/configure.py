"""Generate project-local secrets and the matching S3 auth file without shell evaluation."""

import argparse
import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def configure():
    env_path = ROOT / ".env"
    defaults = {
        "DB_PASSWORD": secrets.token_hex(24),
        "S3_ACCESS_KEY": "sb" + secrets.token_hex(10),
        "S3_SECRET_KEY": secrets.token_hex(32),
        "DEMO_PASSWORD": secrets.token_urlsafe(18),
        "PUBLIC_ORIGIN": "http://localhost:8000",
        "COOKIE_SECURE": "false",
        "BIND_ADDRESS": "127.0.0.1",
        "APP_PORT": "8000",
        "MAX_UPLOAD_BYTES": "536870912",
        "AUTH_RATE_LIMIT": "20",
    }
    if env_path.exists():
        values = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        missing = [key for key in defaults if key not in values]
        if missing:
            raise RuntimeError(
                "Existing .env is missing keys: "
                + ", ".join(missing)
                + ". Preserve existing passwords when completing it."
            )
    else:
        values = defaults
        descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write("# Local secrets. Do not commit or include in the submission ZIP.\n")
            output.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    for key in ("DB_PASSWORD", "S3_SECRET_KEY", "DEMO_PASSWORD"):
        if len(values[key]) < 10 or values[key].startswith("replace-"):
            raise RuntimeError(f"{key} must be a real project-local secret of at least 10 characters")
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True, mode=0o700)
    credentials = {
        "identities": [
            {
                "name": "stackbridge",
                "credentials": [{"accessKey": values["S3_ACCESS_KEY"], "secretKey": values["S3_SECRET_KEY"]}],
                "actions": ["Admin", "Read", "Write", "List", "Tagging"],
            }
        ]
    }
    s3_path = runtime / "s3.json"
    with s3_path.open("w", encoding="utf-8") as output:
        json.dump(credentials, output)
    os.chmod(s3_path, 0o600)
    return values


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-login", action="store_true")
    parser.add_argument("--port", action="store_true")
    args = parser.parse_args()
    values = configure()
    if args.show_login:
        print("Demo logins: viewer, creator, moderator, admin")
        print("Demo password: " + values["DEMO_PASSWORD"])
    elif args.port:
        print(values["APP_PORT"])
    else:
        print("Project-local configuration ready; existing secrets preserved.")
