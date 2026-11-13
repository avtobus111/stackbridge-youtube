"""Verify that an orphaned readiness probe cannot restart PostgreSQL.

Uses only the disposable db service from compose.test.yaml, under a separate
project name. It never connects to the application database. Requires Docker
Compose; run from the source checkout with python3 scripts/check_db_reaping.py.
"""

import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "stackbridge-db-reaping-" + uuid.uuid4().hex[:12]
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", "compose.test.yaml"]
RELEASE = "/tmp/stackbridge-probe-release"
PSQL = 'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h 127.0.0.1 -U tests -d tests -qAt -v ON_ERROR_STOP=1'


def compose(*args, check=True):
    result = subprocess.run(
        [*COMPOSE, *args], cwd=ROOT, capture_output=True, text=True, timeout=150, check=False
    )
    if check and result.returncode:
        raise RuntimeError(f"Docker command failed: {result.stdout}\n{result.stderr}")
    return result


def query(sql):
    return compose("exec", "-T", "db", "sh", "-c", PSQL + ' -c "$1"', "psql", sql, check=False)


def wait_for_tcp():
    # TCP avoids the temporary Unix-only server used by the image's initdb.
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = query("SELECT 1")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        time.sleep(1)
    raise RuntimeError("The disposable PostgreSQL did not become ready over TCP")


def cleanup(witness, primary_failure):
    errors = []
    try:
        try:
            if witness is not None and witness.poll() is None:
                witness.kill()
                witness.communicate(timeout=15)
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(error)
    finally:
        # Docker project teardown must still run if witness teardown times out.
        try:
            compose("down", "--remove-orphans")
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            errors.append(error)
    if errors:
        message = "Diagnostic cleanup failed: " + "; ".join(str(error) for error in errors)
        if primary_failure:
            print(message, file=sys.stderr)
        else:
            raise RuntimeError(message) from errors[0]


def main():
    if compose("ps", "-a", "-q").stdout.strip():
        raise RuntimeError("The diagnostic project already exists; refusing to touch existing containers")
    print(f"Disposable Compose project: {PROJECT}", flush=True)
    witness = None
    try:
        compose("up", "-d", "--wait", "--wait-timeout", "120", "db")
        wait_for_tcp()
        server_pid = compose(
            "exec", "-T", "db", "sh", "-c", 'head -n 1 "$PGDATA/postmaster.pid"'
        ).stdout.strip()
        init_name = compose("exec", "-T", "db", "cat", "/proc/1/comm").stdout.strip()

        # Keep a real connection open across the failure. A shared-memory crash
        # recovery keeps postmaster's PID/start time, but kills its connections.
        witness = subprocess.Popen(
            [*COMPOSE, "exec", "-T", "db", "sh", "-c", PSQL],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        witness.stdin.write("SELECT pg_advisory_lock(34071337); SELECT pg_backend_pid();\n")
        witness.stdin.flush()
        deadline = time.monotonic() + 60
        witness_pid = ""
        while time.monotonic() < deadline:
            result = query("SELECT pid FROM pg_locks WHERE classid=0 AND objid=34071337 AND granted")
            if result.returncode == 0 and result.stdout.strip().isdigit():
                witness_pid = result.stdout.strip()
                break
            time.sleep(0.5)
        if not witness_pid:
            raise RuntimeError("The witness connection did not acquire its advisory lock")

        # Model a timed-out probe shell: its child outlives it, is adopted by
        # PID 1, and then the real pg_isready exits 2 against a closed port.
        # A file barrier makes adoption deterministic instead of racing a sleep.
        probe = (
            f"(while [ ! -f {RELEASE} ]; do sleep 0.1; done; "
            "pg_isready -h 127.0.0.1 -p 65432 -t 1; code=$?; "
            'echo "$code" >/tmp/stackbridge-probe-status; exit "$code") '
            ">/tmp/stackbridge-orphan-probe.log 2>&1 & echo $!"
        )
        orphan_pid = compose("exec", "-T", "db", "sh", "-c", probe).stdout.strip()
        if not orphan_pid.isdigit():
            raise RuntimeError("Could not determine the probe PID")
        status = compose("exec", "-T", "db", "cat", f"/proc/{orphan_pid}/status").stdout
        parent = next(line.split()[1] for line in status.splitlines() if line.startswith("PPid:"))
        if parent != "1":
            raise AssertionError(f"Probe was not orphaned as intended: parent={parent}")
        print(f"Container PID 1={init_name}; postmaster={server_pid}; adopted probe={orphan_pid}", flush=True)
        compose("exec", "-T", "db", "touch", RELEASE)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            exists = compose("exec", "-T", "db", "test", "-e", f"/proc/{orphan_pid}", check=False)
            if exists.returncode:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("The orphaned probe was not reaped")
        code = compose("exec", "-T", "db", "cat", "/tmp/stackbridge-probe-status").stdout.strip()
        print(f"Orphaned readiness probe exited with status {code}", flush=True)
        if code != "2":
            raise RuntimeError(f"The probe did not produce the expected no-response exit: {code}")
        stdout, stderr = witness.communicate("SELECT pg_backend_pid();\n", timeout=30)
        backend_pids = [line.strip() for line in stdout.splitlines() if line.strip().isdigit()]
        logs = compose("logs", "--no-color", "--tail", "40", "db").stdout
        crash = f"server process (PID {orphan_pid}) exited with exit code 2" in logs
        if witness.returncode or backend_pids != [witness_pid, witness_pid] or crash:
            print(logs, flush=True)
            raise AssertionError(
                "The orphaned readiness probe interrupted PostgreSQL: "
                f"probe PID={orphan_pid}, probe crash logged={crash}, "
                f"witness exit={witness.returncode}; {stderr.strip()}"
            )
        print("PASS: orphaned pg_isready was reaped; the same PostgreSQL connection stayed alive")
    finally:
        cleanup(witness, primary_failure=sys.exc_info()[0] is not None)


if __name__ == "__main__":
    main()
