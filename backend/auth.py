import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User, LoginSession, AuthAttempt
from .schemas import Register, Login
from .security import check_origin, digest, hash_password, verify_password, session_for, user_json, require_csrf

router = APIRouter(prefix='/api/auth', tags=['Authentication'])
# Constant work for an unknown username, with a normal scrypt hash.
DUMMY_HASH = hash_password('unusable-dummy-account-password')


def throttle(request, db):
    check_origin(request)
    key = digest(request.client.host if request.client else 'unknown')
    now = time.time()
    attempt = db.scalar(select(AuthAttempt).where(AuthAttempt.key == key).with_for_update())
    if attempt is None:
        attempt = AuthAttempt(key=key, count=0, window=now)
        db.add(attempt)
    if now - attempt.window > 900:
        attempt.count, attempt.window = 0, now
    attempt.count += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(429, 'Слишком много запросов. Повторите позже')
    if attempt.count > settings().auth_rate_limit:
        raise HTTPException(429, 'Слишком много попыток. Повторите через 15 минут', headers={'Retry-After': '900'})


def issue_session(user, request, response, db):
    old = session_for(request, db)
    if old:
        db.delete(old)
    db.execute(delete(LoginSession).where(LoginSession.expires_at < time.time()))
    token = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=digest(token), user_id=user.id, csrf=csrf,
                        expires_at=time.time() + settings().session_days * 86400))
    db.commit()
    response.set_cookie('session', token, max_age=settings().session_days * 86400,
                        httponly=True, secure=settings().cookie_secure, samesite='lax', path='/')
    return {'user': user_json(user), 'csrf_token': csrf}


@router.post('/register', status_code=201)
def register(data: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    user = User(handle=data.handle.lower(), name=data.name, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Этот логин уже занят')
    return issue_session(user, request, response, db)


@router.post('/login')
def login(data: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    user = db.scalar(select(User).where(User.handle == data.handle.lower()))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, 'Неверный логин или пароль')
    return issue_session(user, request, response, db)


@router.get('/me')
def me(request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    session = session_for(request, db)
    user = db.get(User, session.user_id) if session else None
    return {'user': user_json(user) if user else None, 'csrf_token': session.csrf if user else None}


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response, user=Depends(require_csrf), db: Session = Depends(get_db)):
    session = session_for(request, db)
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie('session', path='/', secure=settings().cookie_secure, httponly=True, samesite='lax')

