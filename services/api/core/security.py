"""Authentication, password hashing, credential encryption, and SSRF protection."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from services.api.core.config import get_settings
from services.api.core.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, email: str, expires_hours: int = 24) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc


def _get_fernet() -> Fernet:
    settings = get_settings()
    if settings.credential_encryption_key:
        key = settings.credential_encryption_key.encode("ascii")
    else:
        digest = hashlib.sha256(settings.auth_secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


def sha256_hex(data: str | bytes) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def validate_exploration_url(url: str, registered_base_url: str | None = None) -> str:
    """Validate that an exploration target URL is explicitly allowed and safe from SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Exploration URL must use http or https scheme")
    if not parsed.netloc:
        raise ValueError("Exploration URL must include a valid host")

    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    settings = get_settings()
    allowed = set(settings.allowed_origins_list)
    if registered_base_url:
        reg_parsed = urlparse(registered_base_url)
        if reg_parsed.scheme in ("http", "https") and reg_parsed.netloc:
            allowed.add(f"{reg_parsed.scheme}://{reg_parsed.netloc}".rstrip("/"))

    if origin not in allowed:
        hostname = parsed.hostname or ""
        # Block cloud metadata endpoints & link-local explicitly
        if hostname in ("169.254.169.254", "metadata.google.internal"):
            raise ValueError("Access to cloud metadata endpoints is forbidden")
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_private:
                raise ValueError(f"Target origin {origin} is not in ALLOWED_EXPLORATION_ORIGINS")
        except socket.gaierror as exc:
            raise ValueError(f"Unresolvable target host: {hostname}") from exc
        raise ValueError(f"Target origin {origin} is not explicitly registered or allowed")
    return url


def get_current_user_id(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    token: str | None = creds.credentials if creds else request.cookies.get("mv_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    from services.api.models.schema import User

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user_id
