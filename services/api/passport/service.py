"""Ed25519 Passport signing, verification, JWKS export, and behaviour-to-passport inference."""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from services.api.core.config import get_settings
from services.api.semantic.engine import validate_passport_payload


class PassportVerificationError(ValueError):
    """Raised when a passport fails signature, issuer, expiry, or revocation checks."""


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _load_private_key() -> Ed25519PrivateKey:
    settings = get_settings()
    path = Path(settings.passport_private_key_path)
    if not path.exists():
        raise FileNotFoundError(f"Passport private key not found at {path}. Run scripts/generate_secrets.py")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Passport private key must be Ed25519")
    return key


def _load_public_key() -> Ed25519PublicKey:
    settings = get_settings()
    path = Path(settings.passport_public_key_path)
    if not path.exists():
        raise FileNotFoundError(f"Passport public key not found at {path}. Run scripts/generate_secrets.py")
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Passport public key must be Ed25519")
    return key


def get_jwks() -> dict[str, Any]:
    """Return RFC 8037 OKP Ed25519 public key in JWKS format."""
    settings = get_settings()
    pub = _load_public_key()
    raw_pub = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return {
        "keys": [
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "kid": settings.passport_key_id,
                "use": "sig",
                "alg": "EdDSA",
                "x": _b64u_encode(raw_pub),
            }
        ]
    }


def create_signed_passport(
    preferences: dict[str, Any],
    passport_id: str | None = None,
    version: int = 1,
    subject: str | None = None,
    audience: list[str] | None = None,
    ttl_days: int = 30,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create and sign a compact EdDSA JWS passport token with RFC 8785 canonical payload."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ttl_days)
    pid = passport_id or f"pp_{uuid.uuid4().hex[:16]}"

    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "passport_id": pid,
        "version": version,
        "issuer": settings.passport_issuer,
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "preferences": preferences,
    }
    if subject:
        payload["subject"] = subject
    if audience:
        payload["audience"] = audience
    if scope:
        payload["scope"] = scope

    validate_passport_payload(payload)

    header = {"alg": "EdDSA", "typ": "SFIP-PASSPORT+JWS", "kid": settings.passport_key_id}
    header_b64 = _b64u_encode(rfc8785.dumps(header))
    payload_b64 = _b64u_encode(rfc8785.dumps(payload))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    private_key = _load_private_key()
    signature = private_key.sign(signing_input)
    sig_b64 = _b64u_encode(signature)
    token = f"{header_b64}.{payload_b64}.{sig_b64}"

    return {
        "passport_id": pid,
        "version": version,
        "key_id": settings.passport_key_id,
        "expires_at": expires_at,
        "payload": payload,
        "signature": sig_b64,
        "token": token,
    }


def verify_passport_token(
    token: str,
    expected_audience: str | None = None,
    revoked_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Verify Ed25519 signature, schema, issuer, expiry, audience, and revocation status."""
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise PassportVerificationError("Malformed passport token (expected 3 JWS segments)")

    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64u_decode(header_b64))
        payload = json.loads(_b64u_decode(payload_b64))
        signature = _b64u_decode(sig_b64)
    except Exception as exc:
        raise PassportVerificationError(f"Failed to decode passport token: {exc}") from exc

    if header.get("alg") != "EdDSA":
        raise PassportVerificationError(f"Unsupported passport signature algorithm: {header.get('alg')}")

    pub = _load_public_key()
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        pub.verify(signature, signing_input)
    except InvalidSignature as exc:
        raise PassportVerificationError("Invalid Ed25519 passport signature") from exc

    validate_passport_payload(payload)

    if payload.get("issuer") != settings.passport_issuer:
        raise PassportVerificationError(f"Untrusted passport issuer: {payload.get('issuer')}")

    expires_at = datetime.fromisoformat(payload["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= expires_at:
        raise PassportVerificationError("Passport has expired")

    if revoked_ids and payload["passport_id"] in revoked_ids:
        raise PassportVerificationError("Passport has been revoked")

    if expected_audience and "audience" in payload:
        if expected_audience not in payload["audience"]:
            raise PassportVerificationError(f"Passport not valid for audience '{expected_audience}'")

    return payload


def infer_preferences_from_configuration(
    assignments: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Reverse-map a discovered configuration to portable SFIP preferences, flagging ambiguity."""
    capabilities: dict[str, Any] = manifest.get("capabilities", {})
    inferred: dict[str, Any] = {}
    ambiguous: list[dict[str, Any]] = []
    non_portable: list[str] = []

    for semantic_key, cap in capabilities.items():
        if not cap.get("portable", False):
            non_portable.append(semantic_key)
            continue
        flag_key = cap["flag_key"]
        if flag_key not in assignments:
            continue
        raw_val = assignments[flag_key]
        val = raw_val.get("value") if isinstance(raw_val, dict) and raw_val.get("value") is not None else (
            raw_val.get("enabled") if isinstance(raw_val, dict) else raw_val
        )
        matches = [pref_k for pref_k, mapped_v in cap.get("mapping", {}).items() if mapped_v == val]
        if len(matches) == 1:
            parsed: Any = matches[0]
            if parsed == "true":
                parsed = True
            elif parsed == "false":
                parsed = False
            inferred[semantic_key] = parsed
        elif len(matches) > 1:
            ambiguous.append({
                "semantic_key": semantic_key,
                "flag_key": flag_key,
                "observed_value": val,
                "candidate_preferences": matches,
            })

    return {
        "inferred_preferences": inferred,
        "ambiguous_mappings": ambiguous,
        "non_portable_capabilities": non_portable,
    }
