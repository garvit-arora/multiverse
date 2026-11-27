"""Runtime feature resolution and SDK telemetry observation endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.core.database import get_db
from services.api.runtime.resolver import RuntimeResolutionError, resolve_runtime_experience

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])

# In-memory bounded ring buffer of recent SDK telemetry events (sanitized)
_OBSERVATION_EVENTS: list[dict[str, Any]] = []
SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "api_key", "credit_card"}


class ResolveRequest(BaseModel):
    application_id: str
    passport_token: str | None = None
    preview_token: str | None = None
    user_context: dict[str, Any] = Field(default_factory=dict)
    entitlements: list[str] = Field(default_factory=list)


class ObservationEventRequest(BaseModel):
    application_id: str
    event_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/resolve")
def runtime_resolve(body: ResolveRequest, db: Session = Depends(get_db)):
    try:
        return resolve_runtime_experience(
            db=db,
            application_id=body.application_id,
            user_context=body.user_context,
            passport_token=body.passport_token,
            preview_token=body.preview_token,
            entitlements=body.entitlements,
        )
    except RuntimeResolutionError as exc:
        detail = str(exc)
        code = 503 if "unavailable" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc


@router.post("/observations")
def record_observation_event(body: ObservationEventRequest):
    sanitized = {
        k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else v)
        for k, v in body.metadata.items()
    }
    entry = {
        "application_id": body.application_id,
        "event_name": body.event_name,
        "metadata": sanitized,
    }
    _OBSERVATION_EVENTS.append(entry)
    if len(_OBSERVATION_EVENTS) > 500:
        del _OBSERVATION_EVENTS[:100]
    return {"recorded": True, "event": entry}
