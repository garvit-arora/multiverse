"""Flagsmith integration adapter using official Flagsmith SDK, Management API, and flag-engine."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx
import rfc8785
from flagsmith import Flagsmith
from flagsmith.exceptions import FlagsmithAPIError
from flagsmith.local_evaluation import LocalEvaluation
from flagsmith.models import Flags


class FlagsmithError(Exception):
    """Base error for Flagsmith integration failures."""


class FlagsmithUnavailableError(FlagsmithError):
    """Raised when the Flagsmith instance cannot be reached."""


class FlagsmithAuthError(FlagsmithError):
    """Raised when Flagsmith rejects credentials or tokens."""


@dataclass
class EvaluationResult:
    flags: dict[str, Any]
    source: str  # "flagsmith_sdk" | "flagsmith_engine_snapshot"
    environment_hash: str
    drift_detected: bool = False


class FlagsmithAdapter:
    """Adapter for self-hosted Flagsmith Management API & Identity Evaluation."""

    def __init__(self, api_url: str, management_token: str = "", timeout: float = 10.0) -> None:
        self.api_url = api_url.rstrip("/") + "/"
        self.management_token = management_token
        self.timeout = timeout

    def _mgmt_headers(self) -> dict[str, str]:
        if not self.management_token:
            raise FlagsmithAuthError("Flagsmith Management API token is not configured")
        return {
            "Authorization": f"Token {self.management_token}",
            "Content-Type": "application/json",
        }

    def check_health(self) -> dict[str, Any]:
        """Check connectivity to the Flagsmith API."""
        base = self.api_url.replace("/api/v1/", "")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{base}/health/")
                return {
                    "connected": resp.status_code < 500,
                    "status_code": resp.status_code,
                    "url": self.api_url,
                }
        except httpx.HTTPError as exc:
            return {"connected": False, "error": str(exc), "url": self.api_url}

    def list_organisations(self) -> list[dict[str, Any]]:
        return self._mgmt_get("organisations/")

    def list_projects(self, organisation_id: int | str) -> list[dict[str, Any]]:
        return self._mgmt_get(f"projects/?organisation={organisation_id}")

    def list_environments(self, project_id: int | str) -> list[dict[str, Any]]:
        return self._mgmt_get(f"environments/?project={project_id}")

    def list_features(self, project_id: int | str) -> list[dict[str, Any]]:
        return self._mgmt_get(f"projects/{project_id}/features/")

    def list_feature_states(self, environment_api_key: str) -> list[dict[str, Any]]:
        return self._mgmt_get(f"environments/{environment_api_key}/featurestates/")

    def create_project(self, organisation_id: int | str, name: str) -> dict[str, Any]:
        return self._mgmt_post("projects/", {"name": name, "organisation": organisation_id})

    def create_environment(self, project_id: int | str, name: str) -> dict[str, Any]:
        return self._mgmt_post("environments/", {"name": name, "project": project_id})

    def create_feature(
        self,
        project_id: int | str,
        name: str,
        default_enabled: bool = False,
        initial_value: str | int | float | bool | None = None,
        feature_type: str = "STANDARD",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "default_enabled": default_enabled,
            "type": feature_type,
        }
        if initial_value is not None:
            payload["initial_value"] = str(initial_value)
        return self._mgmt_post(f"projects/{project_id}/features/", payload)

    def get_environment_document(self, environment_api_key: str) -> dict[str, Any]:
        """Fetch environment document from Flagsmith for local engine evaluation & snapshotting."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    f"{self.api_url}environment-document/",
                    headers={"X-Environment-Key": environment_api_key},
                )
                if resp.status_code in (401, 403):
                    raise FlagsmithAuthError("Invalid Flagsmith environment key for environment-document")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as exc:
            raise FlagsmithUnavailableError(f"Cannot reach Flagsmith at {self.api_url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise FlagsmithError(f"Flagsmith environment-document request failed: {exc}") from exc

    @staticmethod
    def hash_document(document: dict[str, Any]) -> str:
        canonical = rfc8785.dumps(document)
        return hashlib.sha256(canonical).hexdigest()

    def evaluate_identity_remote(
        self,
        environment_key: str,
        identifier: str,
        traits: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        """Evaluate an identity directly against the live Flagsmith SDK endpoint."""
        if not environment_key:
            raise FlagsmithAuthError("Flagsmith environment key is required for evaluation")
        try:
            client = Flagsmith(
                environment_key=environment_key,
                api_url=self.api_url,
                request_timeout_seconds=int(self.timeout),
            )
            flags_obj = client.get_identity_flags(identifier=identifier, traits=traits or {})
            evaluated: dict[str, Any] = {}
            for name, flag in flags_obj.all_flags().items():
                evaluated[name] = {
                    "enabled": bool(flag.enabled),
                    "value": flag.value,
                }
            env_hash = hashlib.sha256(rfc8785.dumps(evaluated)).hexdigest()
            return EvaluationResult(flags=evaluated, source="flagsmith_sdk", environment_hash=env_hash)
        except FlagsmithAPIError as exc:
            raise FlagsmithError(f"Flagsmith SDK API error: {exc}") from exc
        except Exception as exc:
            raise FlagsmithUnavailableError(f"Flagsmith evaluation failed: {exc}") from exc

    def evaluate_from_document(
        self,
        environment_document: dict[str, Any],
        identifier: str,
        traits: dict[str, Any] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> EvaluationResult:
        """Evaluate an identity deterministically using Flagsmith's official flag-engine."""
        local_evaluation = LocalEvaluation.from_environment_document(environment_document)
        context, overrides_index = local_evaluation.get_identity_context(identifier, traits or {})
        flags = Flags.from_evaluation_context(
            context=context,
            overrides_index=overrides_index,
            flag_dependent_features=local_evaluation.flag_dependent_features,
            analytics_processor=None,
            default_flag_handler=None,
        )
        evaluated: dict[str, Any] = {}
        for name, fs in flags.all_flags().items():
            evaluated[name] = {
                "enabled": bool(fs.enabled),
                "value": fs.value,
            }
        # Apply explicit sandbox/preview overrides if authorized by policy layer
        if overrides:
            for flag_key, override in overrides.items():
                current = evaluated.get(flag_key, {"enabled": False, "value": None})
                evaluated[flag_key] = {
                    "enabled": override.get("enabled", current["enabled"]),
                    "value": override.get("value", current["value"]),
                }
        return EvaluationResult(
            flags=evaluated,
            source="flagsmith_engine_snapshot",
            environment_hash=self.hash_document(environment_document),
        )

    def detect_drift(self, stored_document_hash: str, environment_api_key: str) -> dict[str, Any]:
        """Compare stored snapshot hash against live Flagsmith environment document."""
        live_doc = self.get_environment_document(environment_api_key)
        live_hash = self.hash_document(live_doc)
        return {
            "drift_detected": live_hash != stored_document_hash,
            "stored_hash": stored_document_hash,
            "live_hash": live_hash,
        }

    def _mgmt_get(self, path: str) -> Any:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.api_url}{path}", headers=self._mgmt_headers())
                if resp.status_code in (401, 403):
                    raise FlagsmithAuthError(f"Flagsmith rejected management token ({resp.status_code})")
                resp.raise_for_status()
                data = resp.json()
                return data.get("results", data) if isinstance(data, dict) and "results" in data else data
        except httpx.ConnectError as exc:
            raise FlagsmithUnavailableError(f"Cannot reach Flagsmith at {self.api_url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise FlagsmithError(f"Flagsmith Management API GET {path} failed: {exc}") from exc

    def _mgmt_post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.api_url}{path}", headers=self._mgmt_headers(), json=payload)
                if resp.status_code in (401, 403):
                    raise FlagsmithAuthError(f"Flagsmith rejected management token ({resp.status_code})")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as exc:
            raise FlagsmithUnavailableError(f"Cannot reach Flagsmith at {self.api_url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise FlagsmithError(f"Flagsmith Management API POST {path} failed: {exc}") from exc
