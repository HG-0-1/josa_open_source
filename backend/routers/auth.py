from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas.journal import (
    AccountDeleteRequest,
    AuthMeOut,
    AuthOut,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from services import auth_service
from services.auth_service import AuthContext


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    _origin: None = Depends(auth_service.verify_origin),
    db: Session = Depends(get_db),
) -> AuthOut:
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="تعذر إنشاء الحساب بهذا البريد الإلكتروني.")
    user = User(email=payload.email, password_hash=auth_service.password_hasher.hash(payload.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="تعذر إنشاء الحساب بهذا البريد الإلكتروني.") from None
    raw_token, csrf_token = auth_service.create_session(db, user)
    auth_service.set_session_cookie(response, raw_token)
    response.headers["Cache-Control"] = "no-store"
    return AuthOut(user=UserOut(id=user.id, email=user.email), csrf_token=csrf_token)


@router.post("/login", response_model=AuthOut)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    _origin: None = Depends(auth_service.verify_origin),
    db: Session = Depends(get_db),
) -> AuthOut:
    client_host = request.client.host if request.client else "unknown"
    key = auth_service.check_login_limit(payload.email, client_host)
    user = db.scalar(select(User).where(User.email == payload.email))
    password_matches = False
    if user is not None:
        try:
            password_matches = auth_service.password_hasher.verify(payload.password, user.password_hash)
        except (ValueError, TypeError):
            password_matches = False
    if user is None or not password_matches:
        auth_service.record_login_failure(key)
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")
    auth_service.clear_login_failures(key)
    raw_token, csrf_token = auth_service.create_session(db, user)
    auth_service.set_session_cookie(response, raw_token)
    response.headers["Cache-Control"] = "no-store"
    return AuthOut(user=UserOut(id=user.id, email=user.email), csrf_token=csrf_token)


@router.get("/me", response_model=AuthMeOut)
async def me(
    response: Response,
    context: AuthContext | None = Depends(auth_service.optional_auth),
) -> AuthMeOut:
    response.headers["Cache-Control"] = "no-store, private"
    if context is None:
        return AuthMeOut(authenticated=False)
    return AuthMeOut(
        authenticated=True,
        user=UserOut(id=context.user.id, email=context.user.email),
        csrf_token=context.session.csrf_token,
    )


@router.post("/logout")
async def logout(
    response: Response,
    context: AuthContext = Depends(auth_service.require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    db.delete(context.session)
    db.commit()
    auth_service.clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


@router.delete("/account")
async def delete_account(
    payload: AccountDeleteRequest,
    response: Response,
    context: AuthContext = Depends(auth_service.require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        valid_password = auth_service.password_hasher.verify(payload.password, context.user.password_hash)
    except (ValueError, TypeError):
        valid_password = False
    if not valid_password:
        raise HTTPException(status_code=403, detail="كلمة المرور غير صحيحة.")
    db.delete(context.user)
    db.commit()
    auth_service.clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}
