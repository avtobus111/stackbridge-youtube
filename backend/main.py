from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from botocore.exceptions import ClientError, BotoCoreError
from sqlalchemy import text
from .db import engine
from .config import settings
from .storage import store, bucket
from . import models  # register database models
from .auth import router as auth_router
from .videos import router as video_router
from .social import router as social_router
from .media import router as media_router, BodyLimitMiddleware


def create_app():
    app = FastAPI(
        title="StackBridge Video API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        description="YouTube-style video app. Sign in, obtain csrf_token from /api/auth/me, and send X-CSRF-Token for mutations. Media endpoints enforce the same permissions as metadata. Moderators and administrators can inspect private videos for moderation.",
    )
    app.include_router(auth_router)
    app.include_router(video_router)
    app.include_router(social_router)
    app.include_router(media_router)
    app.add_middleware(BodyLimitMiddleware)

    @app.get("/docs", include_in_schema=False)
    def docs():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="StackBridge API",
            swagger_js_url="/static/vendor/swagger-ui-bundle.js",
            swagger_css_url="/static/vendor/swagger-ui.css",
            swagger_favicon_url="/static/favicon.svg",
            swagger_ui_parameters={"persistAuthorization": False},
        )

    @app.get("/api/config", tags=["Operations"])
    def public_config():
        return {
            "max_upload_bytes": settings().max_upload_bytes,
            "max_duration_seconds": settings().max_duration_seconds,
        }

    @app.get("/healthz", tags=["Operations"])
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        store().head_bucket(Bucket=bucket())
        return {"ready": True}

    @app.exception_handler(ClientError)
    @app.exception_handler(BotoCoreError)
    async def storage_error(request, error):
        return JSONResponse({"detail": "Хранилище временно недоступно. Повторите попытку"}, 503)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        scripts = "'self' 'unsafe-inline'" if request.url.path == "/docs" else "'self'"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; img-src 'self' data:; media-src 'self'; script-src {scripts}; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    frontend = Path(__file__).resolve().parent.parent / "frontend"
    if frontend.is_dir():
        app.mount("/static", StaticFiles(directory=frontend), name="static")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend_page(path: str):
            if path.startswith(("api/", "static/")):
                raise HTTPException(404, "Not found")
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
