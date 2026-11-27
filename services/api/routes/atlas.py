"""Atlas exploration, SSE progress, behaviour graph, and comparison endpoints."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.atlas.fingerprint import build_behaviour_graph, compute_behaviour_similarity
from services.api.core.config import get_settings
from services.api.core.database import get_db
from services.api.core.security import get_current_user_id
from services.api.models.schema import (
    Application,
    Behaviour,
    BehaviourEdge,
    Configuration,
    Environment,
    ExplorationRun,
    Observation,
    Workflow,
)
from services.api.routes.apps import _get_authorized_app, _user_workspace_ids
from services.worker.tasks import run_exploration_job

router = APIRouter(prefix="/api/v1", tags=["atlas"])


class StartExplorationRequest(BaseModel):
    application_id: str
    environment_id: str | None = None
    workflow_id: str
    strategy: str = Field(default="adaptive", pattern="^(exhaustive|pairwise|adaptive)$")
    budget: int = Field(default=16, ge=1, le=512)
    seed: int = 42
    domains: dict[str, list[Any]]
    constraints: dict[str, Any] | None = None


@router.post("/explorations", status_code=status.HTTP_202_ACCEPTED)
def start_exploration(
    body: StartExplorationRequest,
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
        raise HTTPException(status_code=404, detail="Environment not found for application")
    if env.type == "production":
        raise HTTPException(status_code=400, detail="Exploration mutations are forbidden on production environments")

    wf = db.get(Workflow, body.workflow_id)
    if not wf or wf.application_id != app.id:
        raise HTTPException(status_code=404, detail="Workflow not found for application")

    run = ExplorationRun(
        environment_id=env.id,
        workflow_id=wf.id,
        strategy=body.strategy,
        status="queued",
        budget=body.budget,
        seed=body.seed,
        metrics_json={"executed_count": 0, "budget": body.budget, "distinct_behaviours": 0},
    )
    db.add(run)
    db.commit()

    # Dispatch to RQ if Redis is reachable, otherwise run in background worker thread
    dispatched_via = "thread"
    try:
        from redis import Redis
        from rq import Queue

        settings = get_settings()
        conn = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        conn.ping()
        q = Queue("atlas", connection=conn)
        q.enqueue(run_exploration_job, run.id, body.domains, body.constraints)
        dispatched_via = "rq"
    except Exception:
        t = threading.Thread(
            target=run_exploration_job,
            args=(run.id, body.domains, body.constraints),
            daemon=True,
        )
        t.start()

    return {"id": run.id, "status": run.status, "strategy": run.strategy, "budget": run.budget, "dispatcher": dispatched_via}


@router.get("/explorations")
def list_explorations(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ws_ids = _user_workspace_ids(db, user_id)
    app_ids = [a.id for a in db.query(Application).filter(Application.workspace_id.in_(ws_ids)).all()]
    env_ids = [e.id for e in db.query(Environment).filter(Environment.application_id.in_(app_ids)).all()]
    runs = (
        db.query(ExplorationRun)
        .filter(ExplorationRun.environment_id.in_(env_ids))
        .order_by(ExplorationRun.started_at.desc())
        .limit(50)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "environment_id": r.environment_id,
                "workflow_id": r.workflow_id,
                "strategy": r.strategy,
                "status": r.status,
                "budget": r.budget,
                "seed": r.seed,
                "metrics": r.metrics_json,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]
    }


@router.get("/explorations/{run_id}")
def get_exploration(run_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    run = db.get(ExplorationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Exploration run not found")
    env = db.get(Environment, run.environment_id)
    _get_authorized_app(db, env.application_id, user_id)

    obs_list = db.query(Observation).filter(Observation.run_id == run.id).all()
    return {
        "id": run.id,
        "application_id": env.application_id,
        "environment_id": run.environment_id,
        "workflow_id": run.workflow_id,
        "strategy": run.strategy,
        "status": run.status,
        "budget": run.budget,
        "seed": run.seed,
        "metrics": run.metrics_json,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "observations": [
            {
                "id": o.id,
                "configuration_id": o.configuration_id,
                "behaviour_id": o.behaviour_id,
                "fingerprint": o.fingerprint,
                "status": o.status,
                "duration_ms": o.duration_ms,
                "artifact_path": o.artifact_path,
                "evidence": o.evidence_json,
            }
            for o in obs_list
        ],
    }


@router.get("/explorations/{run_id}/events")
async def exploration_events(run_id: str, db: Session = Depends(get_db)):
    """Real Server-Sent Events stream reporting actual exploration worker progress."""
    run = db.get(ExplorationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Exploration run not found")

    async def event_generator():
        last_sent = -1
        for _ in range(300):
            db.expire_all()
            current = db.get(ExplorationRun, run_id)
            if not current:
                break
            metrics = current.metrics_json or {}
            executed = int(metrics.get("executed_count", 0))
            if executed != last_sent or current.status in ("completed", "failed", "cancelled"):
                last_sent = executed
                payload = json.dumps({
                    "id": current.id,
                    "status": current.status,
                    "metrics": metrics,
                })
                yield f"data: {payload}\n\n"
            if current.status in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/explorations/{run_id}/cancel")
def cancel_exploration(run_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    run = db.get(ExplorationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Exploration run not found")
    env = db.get(Environment, run.environment_id)
    _get_authorized_app(db, env.application_id, user_id)
    run.status = "cancelled"
    db.commit()
    return {"id": run.id, "status": run.status}


@router.get("/apps/{app_id}/atlas")
def get_app_atlas(app_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    _get_authorized_app(db, app_id, user_id)
    behaviours = db.query(Behaviour).filter(Behaviour.application_id == app_id).all()
    if not behaviours:
        return {"application_id": app_id, "nodes": [], "edges": [], "cluster_count": 0}

    b_ids = [b.id for b in behaviours]
    edges = (
        db.query(BehaviourEdge)
        .filter(BehaviourEdge.from_behaviour_id.in_(b_ids), BehaviourEdge.to_behaviour_id.in_(b_ids))
        .all()
    )

    beh_dicts = []
    for b in behaviours:
        obs_count = db.query(Observation).filter(Observation.behaviour_id == b.id).count()
        rep_cfg = db.get(Configuration, b.representative_config_id) if b.representative_config_id else None
        beh_dicts.append({
            "id": b.id,
            "fingerprint": b.fingerprint,
            "workflow_version": b.workflow_version,
            "config_count": max(obs_count, 1),
            "stability_status": b.stability_status,
            "representative_assignments": rep_cfg.assignments_json if rep_cfg else {},
            "summary": b.summary_json,
        })

    edge_dicts = [
        {
            "from_behaviour_id": e.from_behaviour_id,
            "to_behaviour_id": e.to_behaviour_id,
            "flag_delta": e.flag_delta_json,
            "relationship_type": e.relationship_type,
        }
        for e in edges
    ]
    graph = build_behaviour_graph(beh_dicts, edge_dicts)

    # Enrich nodes with representative assignments
    rep_map = {b["id"]: b for b in beh_dicts}
    for n in graph["nodes"]:
        info = rep_map.get(n["id"], {})
        n["representative_assignments"] = info.get("representative_assignments", {})
        n["stability_status"] = info.get("stability_status", "stable")
        n["workflow_version"] = info.get("workflow_version", "1.0")

    return {"application_id": app_id, **graph}


@router.get("/behaviours/compare")
def compare_behaviours(
    a: str = Query(...),
    b: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    beh_a = db.get(Behaviour, a)
    beh_b = db.get(Behaviour, b)
    if not beh_a or not beh_b:
        raise HTTPException(status_code=404, detail="Behaviour not found")
    _get_authorized_app(db, beh_a.application_id, user_id)
    _get_authorized_app(db, beh_b.application_id, user_id)

    rep_a = db.get(Configuration, beh_a.representative_config_id) if beh_a.representative_config_id else None
    rep_b = db.get(Configuration, beh_b.representative_config_id) if beh_b.representative_config_id else None
    sim = compute_behaviour_similarity(beh_a.summary_json, beh_b.summary_json)

    return {
        "behaviour_a": {
            "id": beh_a.id,
            "fingerprint": beh_a.fingerprint,
            "assignments": rep_a.assignments_json if rep_a else {},
            "summary": beh_a.summary_json,
        },
        "behaviour_b": {
            "id": beh_b.id,
            "fingerprint": beh_b.fingerprint,
            "assignments": rep_b.assignments_json if rep_b else {},
            "summary": beh_b.summary_json,
        },
        "similarity": sim,
    }


@router.get("/behaviours/{behaviour_id}")
def get_behaviour(behaviour_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    beh = db.get(Behaviour, behaviour_id)
    if not beh:
        raise HTTPException(status_code=404, detail="Behaviour not found")
    _get_authorized_app(db, beh.application_id, user_id)

    obs = db.query(Observation).filter(Observation.behaviour_id == beh.id).all()
    configs = []
    for o in obs:
        cfg = db.get(Configuration, o.configuration_id)
        if cfg:
            configs.append({
                "observation_id": o.id,
                "configuration_id": cfg.id,
                "configuration_hash": cfg.configuration_hash,
                "assignments": cfg.assignments_json,
                "duration_ms": o.duration_ms,
                "status": o.status,
                "artifact_path": o.artifact_path,
            })

    rep_cfg = db.get(Configuration, beh.representative_config_id) if beh.representative_config_id else None
    return {
        "id": beh.id,
        "application_id": beh.application_id,
        "workflow_version": beh.workflow_version,
        "fingerprint": beh.fingerprint,
        "stability_status": beh.stability_status,
        "summary": beh.summary_json,
        "representative_assignments": rep_cfg.assignments_json if rep_cfg else {},
        "matching_configurations": configs,
    }


@router.get("/artifacts/{run_id}/{filename}")
def get_artifact(run_id: str, filename: str):
    settings = get_settings()
    safe_path = (Path(settings.artifact_storage_path) / run_id / Path(filename).name).resolve()
    base = Path(settings.artifact_storage_path).resolve()
    if not str(safe_path).startswith(str(base)) or not safe_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(safe_path)
