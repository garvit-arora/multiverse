"""Passport Ed25519 creation, verification, revocation, export, and JWKS endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.core.database import get_db
from services.api.core.security import get_current_user_id
from services.api.models.schema import Behaviour, Capability, Configuration, Passport, Preference, Workflow
from services.api.routes.apps import _get_authorized_app
from services.api.passport.service import (
    PassportVerificationError,
    create_signed_passport,
    get_jwks,
    infer_preferences_from_configuration,
    verify_passport_token,
)

router = APIRouter(tags=["passport"])


class CreatePassportRequest(BaseModel):
    preferences: dict[str, Any]
    audience: list[str] | None = None
    ttl_days: int = Field(default=30, ge=1, le=365)
    passport_id: str | None = None
    application_id: str | None = None
    workflow_id: str | None = None


class TokenRequest(BaseModel):
    token: str
    audience: str | None = None


class ExportBehaviourRequest(BaseModel):
    behaviour_id: str
    selected_overrides: dict[str, Any] = Field(default_factory=dict)


@router.get("/.well-known/jwks.json")
def jwks_endpoint():
    return get_jwks()


@router.get("/api/v1/passports")
def list_passports(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    items = db.query(Passport).filter(Passport.user_id == user_id).order_by(Passport.version.desc()).all()
    return {
        "items": [
            {
                "id": p.id,
                "version": p.version,
                "key_id": p.key_id,
                "payload": p.payload_json,
                "expires_at": p.expires_at.isoformat(),
                "revoked_at": p.revoked_at.isoformat() if p.revoked_at else None,
                "signature": p.signature,
            }
            for p in items
        ]
    }


@router.post("/api/v1/passports", status_code=status.HTTP_201_CREATED)
def create_passport(
    body: CreatePassportRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    version = 1
    scope = None
    if body.application_id:
        app = _get_authorized_app(db, body.application_id, user_id)
        workflow = None
        if body.workflow_id:
            workflow = db.get(Workflow, body.workflow_id)
            if not workflow or workflow.application_id != app.id:
                raise HTTPException(status_code=400, detail="Workflow does not belong to the selected application")
        scope = {
            "application_id": app.id,
            "application_name": app.name,
            "build_id": app.build_id,
            **({
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "workflow_version": workflow.version,
            } if workflow else {}),
        }
    if body.passport_id:
        existing = db.get(Passport, body.passport_id)
        if existing:
            version = existing.version + 1
            existing.revoked_at = datetime.now(timezone.utc)

    try:
        signed = create_signed_passport(
            preferences=body.preferences,
            version=version,
            subject=user_id,
            audience=body.audience,
            ttl_days=body.ttl_days,
            scope=scope,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rec = Passport(
        id=signed["passport_id"],
        user_id=user_id,
        version=signed["version"],
        payload_json=signed["payload"],
        signature=signed["signature"],
        key_id=signed["key_id"],
        expires_at=signed["expires_at"],
    )
    db.add(rec)
    db.flush()
    for k, v in body.preferences.items():
        db.add(Preference(passport_id=rec.id, semantic_key=k, value_json=v))
    db.commit()

    return {
        "id": rec.id,
        "version": rec.version,
        "key_id": rec.key_id,
        "payload": rec.payload_json,
        "token": signed["token"],
    }


@router.get("/api/v1/passports/{passport_id}")
def get_passport(passport_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    p = db.get(Passport, passport_id)
    if not p or p.user_id != user_id:
        raise HTTPException(status_code=404, detail="Passport not found")
    return {
        "id": p.id,
        "version": p.version,
        "key_id": p.key_id,
        "payload": p.payload_json,
        "signature": p.signature,
        "expires_at": p.expires_at.isoformat(),
        "revoked_at": p.revoked_at.isoformat() if p.revoked_at else None,
    }


@router.post("/api/v1/passports/verify")
def verify_passport(body: TokenRequest, db: Session = Depends(get_db)):
    revoked_ids = {p.id for p in db.query(Passport).filter(Passport.revoked_at.is_not(None)).all()}
    try:
        payload = verify_passport_token(body.token, expected_audience=body.audience, revoked_ids=revoked_ids)
        return {"valid": True, "payload": payload}
    except PassportVerificationError as exc:
        return {"valid": False, "reason": str(exc)}


@router.post("/api/v1/passports/import")
def import_passport(
    body: TokenRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    revoked_ids = {p.id for p in db.query(Passport).filter(Passport.revoked_at.is_not(None)).all()}
    try:
        payload = verify_passport_token(body.token, expected_audience=body.audience, revoked_ids=revoked_ids)
    except PassportVerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pid = payload["passport_id"]
    if db.get(Passport, pid):
        return {"imported": True, "id": pid, "already_exists": True, "payload": payload}

    rec = Passport(
        id=pid,
        user_id=user_id,
        version=payload["version"],
        payload_json=payload,
        signature=body.token.split(".")[2],
        key_id="imported",
        expires_at=datetime.fromisoformat(payload["expires_at"]),
    )
    db.add(rec)
    db.commit()
    return {"imported": True, "id": pid, "payload": payload}


@router.post("/api/v1/passports/{passport_id}/revoke")
def revoke_passport(passport_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    p = db.get(Passport, passport_id)
    if not p or p.user_id != user_id:
        raise HTTPException(status_code=404, detail="Passport not found")
    p.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": p.id, "revoked": True}


@router.post("/api/v1/passports/export-from-behaviour")
def export_from_behaviour(
    body: ExportBehaviourRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    beh = db.get(Behaviour, body.behaviour_id)
    if not beh:
        raise HTTPException(status_code=404, detail="Behaviour not found")
    rep_cfg = db.get(Configuration, beh.representative_config_id) if beh.representative_config_id else None
    if not rep_cfg:
        raise HTTPException(status_code=400, detail="Behaviour has no representative configuration")

    caps = db.query(Capability).filter(Capability.application_id == beh.application_id).all()
    manifest = {
        "schema_version": "1.0",
        "application": beh.application_id,
        "capabilities": {c.semantic_key: {"flag_key": c.flag_key, **c.mapping_json} for c in caps},
    }
    inferred = infer_preferences_from_configuration(rep_cfg.assignments_json, manifest)
    prefs = dict(inferred["inferred_preferences"])
    prefs.update(body.selected_overrides)

    unresolved_ambiguous = [
        a for a in inferred["ambiguous_mappings"] if a["semantic_key"] not in body.selected_overrides
    ]
    if unresolved_ambiguous:
        return {
            "requires_selection": True,
            "inferred_preferences": prefs,
            "ambiguous_mappings": unresolved_ambiguous,
            "non_portable_capabilities": inferred["non_portable_capabilities"],
        }

    signed = create_signed_passport(preferences=prefs, subject=user_id)
    rec = Passport(
        id=signed["passport_id"],
        user_id=user_id,
        version=signed["version"],
        payload_json=signed["payload"],
        signature=signed["signature"],
        key_id=signed["key_id"],
        expires_at=signed["expires_at"],
    )
    db.add(rec)
    db.commit()
    return {
        "requires_selection": False,
        "passport_id": rec.id,
        "token": signed["token"],
        "payload": signed["payload"],
    }
