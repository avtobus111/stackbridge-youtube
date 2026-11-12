import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User, LoginSession


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${hashed}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split('$')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return algorithm == 'scrypt' and hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def check_origin(request: Request):
    origin = request.headers.get('origin')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Запрос с другого сайта запрещён')
    if origin:
        allowed = {settings().public_origin.rstrip('/'), str(request.base_url).rstrip('/')}
        if origin.rstrip('/') not in allowed or urlsplit(origin).scheme not in ('http', 'https'):
            raise HTTPException(403, 'Запрос с другого сайта запрещён')


def session_for(request: Request, db: Session):
    token = request.cookies.get('session')
    if not token or len(token) > 200:
        return None
    session = db.get(LoginSession, digest(token))
    return session if session and session.expires_at > time.time() else None


def current_user(request: Request, db: Session = Depends(get_db)):
    session = session_for(request, db)
    return db.get(User, session.user_id) if session else None


def require_user(user: User | None = Depends(current_user)):
    if user is None:
        raise HTTPException(401, 'Войдите в аккаунт')
    return user


def require_csrf(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    check_origin(request)
    session = session_for(request, db)
    if not session or not hmac.compare_digest(request.headers.get('x-csrf-token', ''), session.csrf):
        raise HTTPException(403, 'Сессия устарела. Обновите страницу')
    return user


def require_moderator(user: User = Depends(require_user)):
    if user.role not in ('moderator', 'admin'):
        raise HTTPException(403, 'Недостаточно прав')
    return user


def user_json(user: User):
    return {'id': user.id, 'handle': user.handle, 'name': user.name, 'description': user.description,
            'role': user.role, 'color': user.color, 'created_at': user.created_at}

