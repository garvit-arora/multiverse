"""Authentication and workspace endpoints."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from services.api.core.config import get_settings
from services.api.core.database import get_db
from services.api.core.security import (
    create_access_token,
    get_current_user_id,
    hash_password,
    verify_password,
)
from services.api.models.schema import Membership, User, Workspace

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    workspace_name: str = Field(default="Default Workspace", min_length=2, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FirebaseSessionRequest(BaseModel):
    id_token: str = Field(min_length=100, max_length=8192)
    workspace_name: str = Field(default="Default Workspace", min_length=2, max_length=128)


def _set_session_cookie(response: Response, token: str) -> None:
    secure = get_settings().app_base_url.startswith("https://")
    response.set_cookie(
        "mv_session",
        token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        max_age=86400,
        path="/",
    )


def _firebase_admin_app():
    settings = get_settings()
    if not settings.firebase_project_id or not settings.firebase_service_account_path:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase Authentication is not configured on the API.",
        )
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Firebase Authentication dependencies are not installed.") from exc

    try:
        return firebase_admin.get_app("multiverse-auth")
    except ValueError:
        try:
            credential = credentials.Certificate(settings.firebase_service_account_path)
            return firebase_admin.initialize_app(
                credential,
                {"projectId": settings.firebase_project_id},
                name="multiverse-auth",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Firebase Admin credentials could not be loaded.") from exc


def _create_workspace_for_user(db: Session, user: User, workspace_name: str) -> Workspace:
    workspace = Workspace(name=workspace_name, owner_id=user.id)
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    return workspace


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()

    ws = Workspace(name=body.workspace_name, owner_id=user.id)
    db.add(ws)
    db.flush()

    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
    db.commit()

    token = create_access_token(user.id, user.email)
    _set_session_cookie(response, token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
        "workspace": {"id": ws.id, "name": ws.name},
    }


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    ws = db.get(Workspace, membership.workspace_id) if membership else None

    token = create_access_token(user.id, user.email)
    _set_session_cookie(response, token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
        "workspace": {"id": ws.id, "name": ws.name} if ws else None,
    }


@router.post("/firebase")
def firebase_session(
    body: FirebaseSessionRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Exchange a Firebase ID token for a project-scoped Multiverse session."""
    try:
        from firebase_admin import auth as firebase_auth

        decoded = firebase_auth.verify_id_token(body.id_token, app=_firebase_admin_app(), check_revoked=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firebase sign-in token is invalid or expired.") from exc

    email = decoded.get("email")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firebase account must include a verified email.")
    if decoded.get("email_verified") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verify your email address with Firebase, then sign in again.")

    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(48)))
        db.add(user)
        db.flush()

    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    workspace = db.get(Workspace, membership.workspace_id) if membership else None
    if not workspace:
        workspace = _create_workspace_for_user(db, user, body.workspace_name)

    db.commit()
    token = create_access_token(user.id, user.email)
    _set_session_cookie(response, token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
        "workspace": {"id": workspace.id, "name": workspace.name},
    }


@router.post("/logout")
def logout(response: Response):
    secure = get_settings().app_base_url.startswith("https://")
    response.delete_cookie(
        "mv_session",
        path="/",
        secure=secure,
        httponly=True,
        samesite="none" if secure else "lax",
    )
    return {"ok": True}


@router.get("/me")
def me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    memberships = db.query(Membership).filter(Membership.user_id == user_id).all()
    workspaces = [
        {"id": m.workspace_id, "role": m.role, "name": db.get(Workspace, m.workspace_id).name}
        for m in memberships
        if db.get(Workspace, m.workspace_id)
    ]
    return {"id": user.id, "email": user.email, "created_at": user.created_at.isoformat() if user.created_at else None, "workspaces": workspaces}
