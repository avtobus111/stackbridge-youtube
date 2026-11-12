from fastapi import FastAPI
from sqlalchemy import text
from .db import engine
from . import models  # register database models
from .auth import router as auth_router


def create_app():
    app = FastAPI(title='StackBridge Video API', version='1.0.0', description='YouTube-style video app. Sign in, obtain csrf_token from /api/auth/me, and send X-CSRF-Token for mutations. Media endpoints enforce the same permissions as metadata.')
    app.include_router(auth_router)

    @app.get('/healthz', tags=['Operations'])
    def health():
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'ready': True}

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app


app = create_app()

