"""Runtime resolution engine with strict policy precedence, Flagsmith evaluation, and isolated caching."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from services.api.core.config import get_settings
from services.api.core.security import decrypt_secret, sha256_hex
from services.api.flagsmith_adapter.client import (
    FlagsmithAdapter,
    FlagsmithError,
    FlagsmithUnavailableError,
)
from services.api.models.schema import (
    Application,
    Capability,
    Commit,
    Configuration,
    Environment,
    Passport,
    ResolutionLog,
    ShareLink,
    Snapshot,
)
from services.api.passport.service import PassportVerificationError, verify_passport_token
from services.api.semantic.engine import translate_preferences

# In-process request-scoped TTL cache (keyed strictly by isolated tenant/user/passport/preview context)
_RUNTIME_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 15.0


class RuntimeResolutionError(Exception):
    """Raised when runtime resolution cannot safely complete."""


def clear_runtime_cache() -> None:
    _RUNTIME_CACHE.clear()


def _build_cache_key(
    application_id: str,
    env_id: str,
    identity_id: str,
    policy_rev: str,
    passport_hash: str,
    preview_hash: str,
) -> str:
    raw = f"{application_id}:{env_id}:{identity_id}:{policy_rev}:{passport_hash}:{preview_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_app_manifest(db: Session, application: Application) -> dict[str, Any]:
    caps = db.query(Capability).filter(Capability.application_id == application.id).all()
    capabilities_dict: dict[str, Any] = {}
    mandatory_restrictions: dict[str, Any] = {}
    for c in caps:
        capabilities_dict[c.semantic_key] = {
            "flag_key": c.flag_key,
            **c.mapping_json,
        }
        if isinstance(c.policy_json, dict) and "mandatory_restrictions" in c.policy_json:
            mandatory_restrictions.update(c.policy_json["mandatory_restrictions"])

    return {
        "schema_version": "1.0",
        "application": application.id,
        "mandatory_restrictions": mandatory_restrictions,
        "capabilities": capabilities_dict,
    }


def resolve_runtime_experience(
    db: Session,
    application_id: str,
    user_context: dict[str, Any] | None = None,
    passport_token: str | None = None,
    preview_token: str | None = None,
    entitlements: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve a request-scoped Flagsmith-backed feature snapshot enforcing policy precedence."""
    t0 = time.perf_counter()
    user_context = user_context or {}
    identity_id = str(user_context.get("identifier") or user_context.get("user_id") or "anonymous")
    entitlement_set = set(entitlements or [])

    app = db.get(Application, application_id)
    if not app:
        raise RuntimeResolutionError(f"Application '{application_id}' is not registered")

    env = (
        db.query(Environment)
        .filter(Environment.application_id == app.id, Environment.type == "sandbox")
        .first()
        or db.query(Environment).filter(Environment.application_id == app.id).first()
    )
    if not env:
        raise RuntimeResolutionError(f"No Flagsmith environment configured for application '{application_id}'")

    passport_hash = sha256_hex(passport_token) if passport_token else "none"
    preview_hash = sha256_hex(preview_token) if preview_token else "none"
    cache_key = _build_cache_key(app.id, env.id, identity_id, "1.0", passport_hash, preview_hash)

    now_ts = time.monotonic()
    cached = _RUNTIME_CACHE.get(cache_key)
    if cached and cached[0] > now_ts:
        result = dict(cached[1])
        result["cache_hit"] = True
        return result

    diagnostics: dict[str, Any] = {
        "application_id": app.id,
        "environment_id": env.id,
        "identity": identity_id,
        "passport_verified": False,
        "preview_active": False,
        "policy_rejections": [],
        "unsupported_preferences": [],
        "flagsmith_source": None,
        "timings_ms": {},
    }

    # 1. Verify Passport if supplied
    t_pp = time.perf_counter()
    passport_prefs: dict[str, Any] = {}
    passport_id: str | None = None
    if passport_token:
        revoked_ids = {
            p.id for p in db.query(Passport).filter(Passport.revoked_at.is_not(None)).all()
        }
        try:
            payload = verify_passport_token(
                passport_token,
                expected_audience=app.id,
                revoked_ids=revoked_ids,
            )
            passport_prefs = payload.get("preferences", {})
            passport_id = payload.get("passport_id")
            diagnostics["passport_verified"] = True
            diagnostics["passport_id"] = passport_id
        except PassportVerificationError as exc:
            raise RuntimeResolutionError(f"Passport rejected: {exc}") from exc
    diagnostics["timings_ms"]["passport_verify"] = round((time.perf_counter() - t_pp) * 1000, 2)

    # 2. Validate Preview Token if supplied
    preview_overrides: dict[str, dict[str, Any]] = {}
    commit_hash: str | None = None
    if preview_token:
        link = db.query(ShareLink).filter(ShareLink.token_hash == preview_hash).first()
        if not link:
            raise RuntimeResolutionError("Invalid preview token")
        if link.revoked_at is not None:
            raise RuntimeResolutionError("Preview link has been revoked")
        exp = link.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= exp:
            raise RuntimeResolutionError("Preview link has expired")

        commit = db.get(Commit, link.commit_hash)
        if not commit:
            raise RuntimeResolutionError("Preview commit record not found")
        cfg = db.get(Configuration, commit.configuration_id)
        if not cfg:
            raise RuntimeResolutionError("Preview configuration not found")
        commit_hash = commit.commit_hash
        diagnostics["preview_active"] = True
        diagnostics["commit_hash"] = commit_hash
        for fk, fv in cfg.assignments_json.items():
            if isinstance(fv, dict) and "enabled" in fv:
                preview_overrides[fk] = fv
            elif isinstance(fv, bool):
                preview_overrides[fk] = {"enabled": fv, "value": None}
            else:
                preview_overrides[fk] = {"enabled": True, "value": fv}

    # 3. Semantic translation (SFIP)
    t_sem = time.perf_counter()
    manifest = _build_app_manifest(db, app)
    translation = translate_preferences(passport_prefs, manifest, entitlements=entitlement_set)
    diagnostics["policy_rejections"] = translation.rejected
    diagnostics["unsupported_preferences"] = translation.unsupported
    diagnostics["supported_preferences"] = translation.supported
    diagnostics["timings_ms"]["semantic_mapping"] = round((time.perf_counter() - t_sem) * 1000, 2)

    # 4. Precedence merge: preview overrides > passport overrides, subject to mandatory restrictions
    effective_overrides: dict[str, dict[str, Any]] = {}
    effective_overrides.update(translation.flag_overrides)
    effective_overrides.update(preview_overrides)

    # Enforce mandatory restrictions even over preview overrides
    mandatory = manifest.get("mandatory_restrictions", {})
    for fk, forced_val in mandatory.items():
        if fk in effective_overrides:
            current = effective_overrides[fk]
            cur_val = current.get("value") if current.get("value") is not None else current.get("enabled")
            if cur_val != forced_val:
                diagnostics["policy_rejections"].append({
                    "flag_key": fk,
                    "reason": f"Preview/Passport overridden by mandatory restriction ({fk}={forced_val})",
                })
                effective_overrides[fk] = (
                    {"enabled": forced_val, "value": None}
                    if isinstance(forced_val, bool)
                    else {"enabled": True, "value": forced_val}
                )

    # 5. Evaluate through Flagsmith (live SDK or verified environment document snapshot)
    t_fs = time.perf_counter()
    settings = get_settings()
    api_url = app.flagsmith_api_url or settings.flagsmith_api_url
    env_key = decrypt_secret(env.credential_ref) or env.flagsmith_environment_id
    adapter = FlagsmithAdapter(api_url=api_url, management_token=settings.flagsmith_management_api_token)

    evaluated_flags: dict[str, Any] = {}
    latest_snapshot = (
        db.query(Snapshot)
        .filter(Snapshot.environment_id == env.id)
        .order_by(Snapshot.captured_at.desc())
        .first()
    )

    if latest_snapshot and "environment" in latest_snapshot.document_json:
        eval_res = adapter.evaluate_from_document(
            environment_document=latest_snapshot.document_json["environment"],
            identifier=identity_id,
            traits=translation.traits,
            overrides=effective_overrides,
        )
        evaluated_flags = eval_res.flags
        diagnostics["flagsmith_source"] = eval_res.source
    else:
        try:
            eval_res = adapter.evaluate_identity_remote(
                environment_key=env_key,
                identifier=identity_id,
                traits=translation.traits,
            )
            evaluated_flags = dict(eval_res.flags)
            for fk, ov in effective_overrides.items():
                evaluated_flags[fk] = ov
            diagnostics["flagsmith_source"] = eval_res.source
        except (FlagsmithUnavailableError, FlagsmithError) as exc:
            # Never fabricate Flagsmith evaluations silently
            raise RuntimeResolutionError(f"Flagsmith evaluation unavailable: {exc}") from exc

    diagnostics["timings_ms"]["flagsmith_eval"] = round((time.perf_counter() - t_fs) * 1000, 2)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    diagnostics["timings_ms"]["total"] = total_ms

    # 6. Persist resolution log
    db.add(
        ResolutionLog(
            application_id=app.id,
            passport_id=passport_id,
            commit_hash=commit_hash,
            policy_revision="1.0",
            resolved_flags_json=evaluated_flags,
            latency_ms=int(total_ms),
        )
    )
    db.commit()

    response = {
        "application_id": app.id,
        "flags": evaluated_flags,
        "diagnostics": diagnostics,
        "cache_hit": False,
    }
    _RUNTIME_CACHE[cache_key] = (now_ts + CACHE_TTL_SECONDS, response)
    return response
