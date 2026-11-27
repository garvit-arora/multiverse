"""SFIP (Semantic Feature Interoperability Protocol) v1.0 engine."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "packages" / "protocol"
SUPPORTED_SFIP_VERSIONS = {"1.0"}


class ManifestValidationError(ValueError):
    """Raised when an application capability manifest violates SFIP schema."""


@dataclass
class TranslationResult:
    flag_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    supported: list[dict[str, Any]] = field(default_factory=list)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any]) -> None:
    schema_version = manifest.get("schema_version")
    if schema_version not in SUPPORTED_SFIP_VERSIONS:
        raise ManifestValidationError(f"Unsupported SFIP schema_version: {schema_version}")
    try:
        jsonschema.validate(instance=manifest, schema=load_schema("manifest.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ManifestValidationError(f"Invalid SFIP manifest: {exc.message}") from exc


def validate_passport_payload(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_SFIP_VERSIONS:
        raise ManifestValidationError(f"Unsupported passport schema_version: {schema_version}")
    try:
        jsonschema.validate(instance=payload, schema=load_schema("passport.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ManifestValidationError(f"Invalid passport payload: {exc.message}") from exc


def translate_preferences(
    preferences: dict[str, Any],
    manifest: dict[str, Any],
    entitlements: set[str] | None = None,
) -> TranslationResult:
    """Translate universal SFIP preferences into Flagsmith-backed flag overrides and traits."""
    validate_manifest(manifest)
    entitlements = entitlements or set()
    capabilities: dict[str, Any] = manifest.get("capabilities", {})
    aliases: dict[str, str] = manifest.get("aliases", {})
    mandatory_restrictions: dict[str, Any] = manifest.get("mandatory_restrictions", {})

    result = TranslationResult()
    flag_claims: dict[str, list[tuple[str, Any, int]]] = {}

    for raw_key, pref_value in preferences.items():
        semantic_key = aliases.get(raw_key, raw_key)
        cap = capabilities.get(semantic_key)
        if not cap:
            result.unsupported.append({
                "semantic_key": raw_key,
                "reason": "Capability not declared in application manifest",
            })
            continue

        if not cap.get("user_configurable", True):
            result.rejected.append({
                "semantic_key": semantic_key,
                "reason": "Capability is locked by application policy (user_configurable=false)",
            })
            continue

        req_entitlement = cap.get("requires_entitlement")
        if req_entitlement and req_entitlement not in entitlements:
            result.rejected.append({
                "semantic_key": semantic_key,
                "reason": f"Missing required server-verified entitlement: {req_entitlement}",
            })
            continue

        mapping = cap.get("mapping", {})
        lookup_key = str(pref_value).lower() if isinstance(pref_value, bool) else str(pref_value)
        if lookup_key not in mapping:
            result.rejected.append({
                "semantic_key": semantic_key,
                "reason": f"Preference value '{pref_value}' has no approved mapping",
            })
            continue

        mapped_value = mapping[lookup_key]
        flag_key = cap["flag_key"]

        # Check mandatory security restrictions
        if flag_key in mandatory_restrictions:
            forced = mandatory_restrictions[flag_key]
            if mapped_value != forced:
                result.rejected.append({
                    "semantic_key": semantic_key,
                    "flag_key": flag_key,
                    "reason": f"Blocked by mandatory application security restriction ({flag_key}={forced})",
                })
                continue

        priority = int(cap.get("priority", 50))
        flag_claims.setdefault(flag_key, []).append((semantic_key, mapped_value, priority))

        trait_key = cap.get("trait_key")
        if trait_key:
            result.traits[trait_key] = pref_value

        result.supported.append({
            "semantic_key": semantic_key,
            "preference_value": pref_value,
            "flag_key": flag_key,
            "mapped_value": mapped_value,
        })

    # Resolve multiple capabilities targeting the same flag deterministically by priority + key
    for flag_key, claims in flag_claims.items():
        unique_values = {repr(val) for _, val, _ in claims}
        if len(unique_values) > 1:
            claims_sorted = sorted(claims, key=lambda c: (-c[2], c[0]))
            winner_key, winner_val, winner_prio = claims_sorted[0]
            result.conflicts.append({
                "flag_key": flag_key,
                "winning_capability": winner_key,
                "winning_priority": winner_prio,
                "claims": [{"capability": k, "value": v, "priority": p} for k, v, p in claims_sorted],
            })
            chosen = winner_val
        else:
            chosen = claims[0][1]

        if isinstance(chosen, bool):
            result.flag_overrides[flag_key] = {"enabled": chosen, "value": None}
        else:
            result.flag_overrides[flag_key] = {"enabled": True, "value": chosen}

    return result
