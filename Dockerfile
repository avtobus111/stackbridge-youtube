FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app
COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app backend ./backend
COPY --chown=app:app frontend ./frontend
COPY --chown=app:app assets ./assets
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini pyproject.toml ./
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM python:3.12-slim-bookworm AS test
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app
COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements-test.txt
COPY --chown=app:app backend ./backend
COPY --chown=app:app frontend ./frontend
COPY --chown=app:app assets ./assets
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app tests ./tests
COPY --chown=app:app alembic.ini pyproject.toml ./
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

