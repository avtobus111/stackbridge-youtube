import subprocess

import pytest

from scripts import check_db_reaping


class BrokenWitness:
    def __init__(self, failure):
        self.failure = failure

    def poll(self):
        return None

    def kill(self):
        if self.failure == "kill":
            raise ProcessLookupError("witness exited during teardown")

    def communicate(self, timeout):
        raise subprocess.TimeoutExpired("docker exec witness", timeout)


@pytest.mark.parametrize("failure", ["kill", "communicate"])
def test_project_teardown_runs_and_preserves_original_probe_failure(monkeypatch, failure):
    calls = []
    monkeypatch.setattr(check_db_reaping, "compose", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="original probe failure"):
        try:
            raise ValueError("original probe failure")
        finally:
            check_db_reaping.cleanup(BrokenWitness(failure), primary_failure=True)
    assert calls == [("down", "--remove-orphans")]


def test_cleanup_failure_after_success_makes_the_regression_fail(monkeypatch):
    calls = []
    monkeypatch.setattr(check_db_reaping, "compose", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="cleanup"):
        check_db_reaping.cleanup(BrokenWitness("communicate"), primary_failure=False)
    assert calls == [("down", "--remove-orphans")]
