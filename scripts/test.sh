#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")/.."
trap 'docker compose -p stackbridge-test -f compose.test.yaml down --remove-orphans' EXIT
docker compose -p stackbridge-test -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests

