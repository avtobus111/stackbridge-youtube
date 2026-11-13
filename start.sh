#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"

if ! command -v docker >/dev/null 2>&1; then
  if [[ "${EUID}" -ne 0 ]]; then
    echo 'Docker is missing. On clean Ubuntu run: sudo bash start.sh' >&2
    exit 1
  fi
  . /etc/os-release
  if [[ "$ID" != ubuntu ]]; then
    echo 'Automatic Docker installation supports Ubuntu. Install Docker Engine and Compose, then rerun.' >&2
    exit 1
  fi
  apt-get update
  apt-get install -y ca-certificates curl python3
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$(dpkg --print-architecture)" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo 'python3 is required to generate local secrets. Install it with apt-get install python3.' >&2
  exit 1
fi
docker compose version >/dev/null
if ! docker info >/dev/null 2>&1; then
  if [[ "${EUID}" -eq 0 ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl start docker
  else
    echo 'Docker Engine is not running or this user has no access. Start Docker or run with sudo.' >&2
    exit 1
  fi
fi
python3 scripts/configure.py
docker compose config --quiet
if ! docker compose up -d --build --wait --wait-timeout 600; then
  docker compose logs --tail 60 storage db initialize web worker
  exit 1
fi
APP_PORT="$(python3 scripts/configure.py --port)"
printf '\nOpen http://localhost:%s (Swagger: /docs).\n' "$APP_PORT"
python3 scripts/configure.py --show-login
echo 'Default binding is loopback only. See README for remote evaluation and TLS settings.'

