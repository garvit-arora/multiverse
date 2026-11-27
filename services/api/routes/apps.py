"""Application registry, Flagsmith connection, capability manifests, and workflow endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.core.config import get_settings
from services.api.core.database import get_db
from services.api.core.security import encrypt_secret, get_current_user_id, validate_exploration_url
from services.api.flagsmith_adapter.client import FlagsmithAdapter, FlagsmithError
from services.api.models.schema import (
    Application,
    Branch,
    Capability,
    Environment,
    ExplorationRun,
    Membership,
    Snapshot,
    Workspace,
    Workflow,
)
from services.api.semantic.engine import ManifestValidationError, validate_manifest

router = APIRouter(prefix="/api/v1/apps", tags=["applications"])


def _user_workspace_ids(db: Session, user_id: str) -> list[str]:
    return [m.workspace_id for m in db.query(Membership).filter(Membership.user_id == user_id).all()]


def _get_authorized_app(db: Session, app_id: str, user_id: str) -> Application:
    app = db.get(Application, app_id)
    if not app or app.workspace_id not in _user_workspace_ids(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


class CreateAppRequest(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    base_url: str = Field(min_length=4, max_length=512)
    build_id: str = Field(default="build-0.1.0", max_length=64)
    flagsmith_api_url: str | None = None
    flagsmith_project_id: str | None = None
    environment_key: str | None = None
    environment_type: str = "sandbox"


class ConnectFlagsmithRequest(BaseModel):
    flagsmith_api_url: str
    environment_key: str
    environment_name: str = "sandbox"
    environment_type: str = "sandbox"
    management_token: str | None = None


class RegisterWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    version: str = "1.0"
    definition: dict[str, Any]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_app(
    body: CreateAppRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ws_ids = _user_workspace_ids(db, user_id)
    if not ws_ids:
        raise HTTPException(status_code=400, detail="User has no workspace")
    try:
        validate_exploration_url(body.base_url, registered_base_url=body.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    app_id = body.id or body.name.lower().replace(" ", "-")
    if db.get(Application, app_id):
        raise HTTPException(status_code=409, detail=f"Application '{app_id}' already exists")

    app = Application(
        id=app_id,
        workspace_id=ws_ids[0],
        name=body.name,
        base_url=body.base_url,
        build_id=body.build_id,
        flagsmith_api_url=body.flagsmith_api_url or get_settings().flagsmith_api_url,
        flagsmith_project_id=body.flagsmith_project_id,
    )
    db.add(app)
    db.flush()

    if body.environment_key:
        env = Environment(
            application_id=app.id,
            name=body.environment_type,
            flagsmith_environment_id=body.environment_key[:16],
            credential_ref=encrypt_secret(body.environment_key),
            type=body.environment_type,
        )
        db.add(env)

    db.commit()
    return {"id": app.id, "name": app.name, "base_url": app.base_url, "build_id": app.build_id}


@router.get("")
def list_apps(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ws_ids = _user_workspace_ids(db, user_id)
    apps = db.query(Application).filter(Application.workspace_id.in_(ws_ids)).all()
    out = []
    for a in apps:
        workspace = db.get(Workspace, a.workspace_id)
        envs = db.query(Environment).filter(Environment.application_id == a.id).all()
        caps = db.query(Capability).filter(Capability.application_id == a.id).all()
        wfs = db.query(Workflow).filter(Workflow.application_id == a.id).all()
        out.append({
            "id": a.id,
            "workspace_id": a.workspace_id,
            "workspace_name": workspace.name if workspace else "Unknown workspace",
            "can_delete": bool(workspace and workspace.owner_id == user_id),
            "name": a.name,
            "base_url": a.base_url,
            "build_id": a.build_id,
            "flagsmith_api_url": a.flagsmith_api_url,
            "environments": [{"id": e.id, "name": e.name, "type": e.type} for e in envs],
            "capability_count": len(caps),
            "workflow_count": len(wfs),
        })
    return {"items": out}


@router.get("/{app_id}")
def get_app(app_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    app = _get_authorized_app(db, app_id, user_id)
    envs = db.query(Environment).filter(Environment.application_id == app.id).all()
    caps = db.query(Capability).filter(Capability.application_id == app.id).all()
    wfs = db.query(Workflow).filter(Workflow.application_id == app.id).all()
    return {
        "id": app.id,
        "name": app.name,
        "base_url": app.base_url,
        "build_id": app.build_id,
        "flagsmith_api_url": app.flagsmith_api_url,
        "environments": [{"id": e.id, "name": e.name, "type": e.type, "flagsmith_environment_id": e.flagsmith_environment_id} for e in envs],
        "capabilities": [
            {"semantic_key": c.semantic_key, "flag_key": c.flag_key, "mapping": c.mapping_json, "policy": c.policy_json}
            for c in caps
        ],
        "workflows": [{"id": w.id, "name": w.name, "version": w.version, "definition": w.definition_json} for w in wfs],
    }


@router.delete("/{app_id}")
def delete_app(app_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    app = _get_authorized_app(db, app_id, user_id)
    workspace = db.get(Workspace, app.workspace_id)
    if not workspace or workspace.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the workspace owner can remove this project")

    environment_ids = [row.id for row in db.query(Environment.id).filter(Environment.application_id == app.id).all()]
    if environment_ids:
        active = db.query(ExplorationRun.id).filter(
            ExplorationRun.environment_id.in_(environment_ids),
            ExplorationRun.status.in_(["queued", "running"]),
        ).first()
        if active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stop active Atlas explorations before removing this project")
        # Branch heads restrict deletion of their commits, so remove project branches before cascading project data.
        db.query(Branch).filter(Branch.environment_id.in_(environment_ids)).delete(synchronize_session=False)

    db.delete(app)
    db.commit()
    return {"id": app_id, "deleted": True}


@router.post("/{app_id}/connect")
def connect_flagsmith(
    app_id: str,
    body: ConnectFlagsmithRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    app = _get_authorized_app(db, app_id, user_id)
    adapter = FlagsmithAdapter(
        api_url=body.flagsmith_api_url,
        management_token=body.management_token or get_settings().flagsmith_management_api_token,
    )
    health = adapter.check_health()
    if not health.get("connected"):
        raise HTTPException(
            status_code=503,
            detail=f"Flagsmith unreachable at {body.flagsmith_api_url}: {health.get('error', 'unhealthy')}",
        )

    try:
        environment_document = adapter.get_environment_document(body.environment_key)
    except FlagsmithError as exc:
        raise HTTPException(status_code=400, detail=f"Environment key validation failed: {exc}") from exc

    app.flagsmith_api_url = body.flagsmith_api_url
    matches = db.query(Environment).filter(
        Environment.application_id == app.id,
        Environment.name == body.environment_name,
    ).all()
    env = matches[0] if matches else Environment(application_id=app.id, name=body.environment_name)
    env.flagsmith_environment_id = body.environment_key[:16]
    env.credential_ref = encrypt_secret(body.environment_key)
    env.type = body.environment_type
    if not matches:
        db.add(env)
    for duplicate in matches[1:]:
        db.delete(duplicate)
    db.commit()
    return {
        "connected": True,
        "environment_id": env.id,
        "flagsmith": health,
        "feature_count": len(environment_document.get("features", [])),
    }


@router.post("/{app_id}/sync")
def sync_flagsmith(
    app_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    app = _get_authorized_app(db, app_id, user_id)
    env = db.query(Environment).filter(Environment.application_id == app.id).first()
    if not env:
        raise HTTPException(status_code=400, detail="No Flagsmith environment connected")

    from services.api.core.security import decrypt_secret

    env_key = decrypt_secret(env.credential_ref)
    adapter = FlagsmithAdapter(
        api_url=app.flagsmith_api_url or get_settings().flagsmith_api_url,
        management_token=get_settings().flagsmith_management_api_token,
    )
    try:
        doc = adapter.get_environment_document(env_key)
        doc_hash = adapter.hash_document(doc)
    except FlagsmithError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    snap = Snapshot(
        environment_id=env.id,
        document_hash=doc_hash,
        document_json={"environment": doc},
    )
    db.add(snap)
    db.commit()
    return {"synced": True, "snapshot_id": snap.id, "document_hash": doc_hash}


@router.put("/{app_id}/capabilities")
def update_capabilities(
    app_id: str,
    manifest: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    app = _get_authorized_app(db, app_id, user_id)
    try:
        validate_manifest(manifest)
    except ManifestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.query(Capability).filter(Capability.application_id == app.id).delete()
    mandatory = manifest.get("mandatory_restrictions", {})
    for sem_key, spec in manifest.get("capabilities", {}).items():
        flag_key = spec["flag_key"]
        db.add(
            Capability(
                application_id=app.id,
                semantic_key=sem_key,
                flag_key=flag_key,
                mapping_json={k: v for k, v in spec.items() if k != "flag_key"},
                policy_json={"mandatory_restrictions": mandatory} if mandatory else {},
            )
        )
    db.commit()
    return {"updated": True, "capability_count": len(manifest.get("capabilities", {}))}


@router.post("/{app_id}/workflows", status_code=status.HTTP_201_CREATED)
def register_workflow(
    app_id: str,
    body: RegisterWorkflowRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    app = _get_authorized_app(db, app_id, user_id)
    wf = Workflow(
        application_id=app.id,
        name=body.name,
        version=body.version,
        definition_json=body.definition,
    )
    db.add(wf)
    db.commit()
    return {"id": wf.id, "name": wf.name, "version": wf.version}
