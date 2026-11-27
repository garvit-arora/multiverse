"""Verse behavioural version control endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.core.database import get_db
from services.api.core.security import get_current_user_id
from services.api.models.schema import (
    Application,
    Behaviour,
    Branch,
    Commit,
    CommitParent,
    Configuration,
    Environment,
    ShareLink,
)
from services.api.routes.apps import _get_authorized_app, _user_workspace_ids
from services.api.verse.service import (
    ConcurrencyError,
    create_commit_record,
    create_preview_share_link,
    diff_configurations,
    find_common_ancestor,
    three_way_merge,
    update_branch_head,
)

router = APIRouter(prefix="/api/v1", tags=["verse"])


class CreateBranchRequest(BaseModel):
    application_id: str
    environment_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    from_behaviour_id: str | None = None
    from_commit_hash: str | None = None
    assignments: dict[str, Any] | None = None
    message: str = "Initial branch commit"


class CreateCommitRequest(BaseModel):
    assignments: dict[str, Any]
    message: str = Field(min_length=1, max_length=512)
    expected_revision: int


class MergeRequest(BaseModel):
    source_branch_id: str
    destination_branch_id: str
    resolutions: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class ShareCommitRequest(BaseModel):
    ttl_hours: int = Field(default=24, ge=1, le=720)


@router.get("/branches")
def list_branches(
    application_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ws_ids = _user_workspace_ids(db, user_id)
    apps = db.query(Application).filter(Application.workspace_id.in_(ws_ids)).all()
    app_ids = [application_id] if application_id else [a.id for a in apps]
    envs = db.query(Environment).filter(Environment.application_id.in_(app_ids)).all()
    env_map = {e.id: e for e in envs}
    branches = db.query(Branch).filter(Branch.environment_id.in_(list(env_map.keys()))).all()

    out = []
    for b in branches:
        commit = db.get(Commit, b.head_commit_hash)
        cfg = db.get(Configuration, commit.configuration_id) if commit else None
        out.append({
            "id": b.id,
            "environment_id": b.environment_id,
            "application_id": env_map[b.environment_id].application_id,
            "name": b.name,
            "head_commit_hash": b.head_commit_hash,
            "revision": b.revision,
            "assignments": cfg.assignments_json if cfg else {},
            "head_message": commit.message if commit else "",
            "created_at": commit.created_at.isoformat() if commit else None,
        })
    return {"items": out}


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def create_branch(
    body: CreateBranchRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    app = _get_authorized_app(db, body.application_id, user_id)
    env = (
        db.get(Environment, body.environment_id)
        if body.environment_id
        else db.query(Environment).filter(Environment.application_id == app.id).first()
    )
    if not env or env.application_id != app.id:
        raise HTTPException(status_code=404, detail="Environment not found")

    if db.query(Branch).filter(Branch.environment_id == env.id, Branch.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"Branch '{body.name}' already exists")

    head_hash: str
    if body.from_commit_hash:
        commit = db.get(Commit, body.from_commit_hash)
        if not commit:
            raise HTTPException(status_code=404, detail="Source commit not found")
        head_hash = commit.commit_hash
    else:
        assignments = body.assignments or {}
        evidence_beh_id: str | None = None
        if body.from_behaviour_id:
            beh = db.get(Behaviour, body.from_behaviour_id)
            if not beh or beh.application_id != app.id:
                raise HTTPException(status_code=404, detail="Behaviour not found")
            evidence_beh_id = beh.id
            rep_cfg = db.get(Configuration, beh.representative_config_id) if beh.representative_config_id else None
            if rep_cfg and not assignments:
                assignments = rep_cfg.assignments_json

        commit = create_commit_record(
            db,
            environment_id=env.id,
            assignments=assignments,
            author_id=user_id,
            message=body.message,
            build_id=app.build_id,
            evidence_behaviour_id=evidence_beh_id,
        )
        head_hash = commit.commit_hash

    branch = Branch(environment_id=env.id, name=body.name, head_commit_hash=head_hash, revision=1)
    db.add(branch)
    db.commit()
    return {
        "id": branch.id,
        "name": branch.name,
        "environment_id": branch.environment_id,
        "head_commit_hash": branch.head_commit_hash,
        "revision": branch.revision,
    }


@router.get("/branches/{branch_id}/history")
def branch_history(branch_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    branch = db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    env = db.get(Environment, branch.environment_id)
    _get_authorized_app(db, env.application_id, user_id)

    visited: set[str] = set()
    history = []
    queue = [branch.head_commit_hash]
    while queue and len(history) < 100:
        ch = queue.pop(0)
        if ch in visited:
            continue
        visited.add(ch)
        c = db.get(Commit, ch)
        if not c:
            continue
        cfg = db.get(Configuration, c.configuration_id)
        parents = [
            p.parent_hash
            for p in db.query(CommitParent).filter(CommitParent.commit_hash == ch).order_by(CommitParent.parent_order).all()
        ]
        queue.extend(parents)
        history.append({
            "commit_hash": c.commit_hash,
            "message": c.message,
            "author_id": c.author_id,
            "build_id": c.build_id,
            "parents": parents,
            "assignments": cfg.assignments_json if cfg else {},
            "evidence_behaviour_id": c.evidence_behaviour_id,
            "created_at": c.created_at.isoformat(),
        })
    return {"branch": {"id": branch.id, "name": branch.name, "revision": branch.revision}, "commits": history}


@router.post("/branches/{branch_id}/commits", status_code=status.HTTP_201_CREATED)
def create_commit(
    branch_id: str,
    body: CreateCommitRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    branch = db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    env = db.get(Environment, branch.environment_id)
    app = _get_authorized_app(db, env.application_id, user_id)

    commit = create_commit_record(
        db,
        environment_id=env.id,
        assignments=body.assignments,
        author_id=user_id,
        message=body.message,
        parent_hashes=[branch.head_commit_hash],
        build_id=app.build_id,
    )
    try:
        update_branch_head(db, branch, commit.commit_hash, body.expected_revision)
    except ConcurrencyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    return {"commit_hash": commit.commit_hash, "branch_revision": branch.revision}


@router.get("/branches/diff")
def diff_branches(
    base: str = Query(...),
    target: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    b_base = db.get(Branch, base)
    b_target = db.get(Branch, target)
    if not b_base or not b_target:
        raise HTTPException(status_code=404, detail="Branch not found")
    c_base = db.get(Commit, b_base.head_commit_hash)
    c_target = db.get(Commit, b_target.head_commit_hash)
    cfg_base = db.get(Configuration, c_base.configuration_id)
    cfg_target = db.get(Configuration, c_target.configuration_id)
    d = diff_configurations(cfg_base.assignments_json, cfg_target.assignments_json)
    return {
        "base": {"id": b_base.id, "name": b_base.name, "commit_hash": c_base.commit_hash},
        "target": {"id": b_target.id, "name": b_target.name, "commit_hash": c_target.commit_hash},
        "diff": {
            "added": d.added,
            "removed": d.removed,
            "changed": d.changed,
            "unchanged_count": d.unchanged_count,
        },
    }


@router.post("/merge/preview")
def preview_merge(body: MergeRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    src = db.get(Branch, body.source_branch_id)
    dst = db.get(Branch, body.destination_branch_id)
    if not src or not dst:
        raise HTTPException(status_code=404, detail="Branch not found")

    lca_hash = find_common_ancestor(db, src.head_commit_hash, dst.head_commit_hash)
    src_cfg = db.get(Configuration, db.get(Commit, src.head_commit_hash).configuration_id).assignments_json
    dst_cfg = db.get(Configuration, db.get(Commit, dst.head_commit_hash).configuration_id).assignments_json
    anc_cfg = (
        db.get(Configuration, db.get(Commit, lca_hash).configuration_id).assignments_json
        if lca_hash
        else {}
    )

    merged, conflicts = three_way_merge(anc_cfg, src_cfg, dst_cfg)
    return {
        "common_ancestor": lca_hash,
        "merged_assignments": merged,
        "conflicts": conflicts,
        "can_auto_merge": len(conflicts) == 0,
    }


@router.post("/merge/execute")
def execute_merge(body: MergeRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    src = db.get(Branch, body.source_branch_id)
    dst = db.get(Branch, body.destination_branch_id)
    if not src or not dst:
        raise HTTPException(status_code=404, detail="Branch not found")
    env = db.get(Environment, dst.environment_id)
    app = _get_authorized_app(db, env.application_id, user_id)

    lca_hash = find_common_ancestor(db, src.head_commit_hash, dst.head_commit_hash)
    src_cfg = db.get(Configuration, db.get(Commit, src.head_commit_hash).configuration_id).assignments_json
    dst_cfg = db.get(Configuration, db.get(Commit, dst.head_commit_hash).configuration_id).assignments_json
    anc_cfg = (
        db.get(Configuration, db.get(Commit, lca_hash).configuration_id).assignments_json
        if lca_hash
        else {}
    )

    merged, conflicts = three_way_merge(anc_cfg, src_cfg, dst_cfg)
    unresolved = [c for c in conflicts if c["key"] not in body.resolutions]
    if unresolved:
        raise HTTPException(status_code=409, detail={"message": "Unresolved merge conflicts", "conflicts": unresolved})

    for k, val in body.resolutions.items():
        merged[k] = val

    msg = body.message or f"Merge '{src.name}' into '{dst.name}'"
    merge_commit = create_commit_record(
        db,
        environment_id=dst.environment_id,
        assignments=merged,
        author_id=user_id,
        message=msg,
        parent_hashes=[dst.head_commit_hash, src.head_commit_hash],
        build_id=app.build_id,
    )
    update_branch_head(db, dst, merge_commit.commit_hash, dst.revision)
    db.commit()
    return {"commit_hash": merge_commit.commit_hash, "branch_id": dst.id, "revision": dst.revision, "merged": merged}


@router.post("/commits/{commit_hash}/share", status_code=status.HTTP_201_CREATED)
def share_commit(
    commit_hash: str,
    body: ShareCommitRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    commit = db.get(Commit, commit_hash)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    link, raw_token = create_preview_share_link(db, commit_hash, ttl_hours=body.ttl_hours)
    db.commit()
    return {
        "id": link.id,
        "commit_hash": link.commit_hash,
        "preview_token": raw_token,
        "expires_at": link.expires_at.isoformat(),
    }


@router.get("/shares")
def list_shares(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    links = db.query(ShareLink).order_by(ShareLink.expires_at.desc()).limit(50).all()
    return {
        "items": [
            {
                "id": link.id,
                "commit_hash": link.commit_hash,
                "expires_at": link.expires_at.isoformat(),
                "revoked_at": link.revoked_at.isoformat() if link.revoked_at else None,
            }
            for link in links
        ]
    }


@router.delete("/shares/{share_id}")
def revoke_share(share_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    link = db.get(ShareLink, share_id)
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")
    link.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": link.id, "revoked": True}
