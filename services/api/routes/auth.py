"""Authentication and workspace endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

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
    response.set_cookie("mv_session", token, httponly=True, samesite="lax", max_age=86400)
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
    response.set_cookie("mv_session", token, httponly=True, samesite="lax", max_age=86400)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
        "workspace": {"id": ws.id, "name": ws.name} if ws else None,
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("mv_session")
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
