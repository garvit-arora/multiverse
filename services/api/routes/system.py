"""System health, readiness, status, and real computed analytics/metrics endpoints."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from services.api.core.config import get_settings
from services.api.core.database import get_db
from services.api.flagsmith_adapter.client import FlagsmithAdapter
from services.api.models.schema import (
    Application,
    Behaviour,
    Branch,
    Commit,
    ExplorationRun,
    Observation,
    Passport,
    ResolutionLog,
)

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "multiverse-api"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        from redis import Redis

        r = Redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "ready": db_ok,
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
    }


@router.get("/api/v1/system/status")
def system_status(db: Session = Depends(get_db)):
    settings = get_settings()
    adapter = FlagsmithAdapter(api_url=settings.flagsmith_api_url)
    fs_health = adapter.check_health()

    redis_ok = False
    try:
        from redis import Redis

        r = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "api": "ok",
        "flagsmith": fs_health,
        "redis": {"connected": redis_ok},
        "counts": {
            "applications": db.query(Application).count(),
            "behaviours": db.query(Behaviour).count(),
            "exploration_runs": db.query(ExplorationRun).count(),
            "observations": db.query(Observation).count(),
            "branches": db.query(Branch).count(),
            "commits": db.query(Commit).count(),
            "active_passports": db.query(Passport).filter(Passport.revoked_at.is_(None)).count(),
        },
    }


@router.get("/api/v1/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """Return real computed metrics from persisted exploration runs, observations, and runtime resolution logs."""
    runs = db.query(ExplorationRun).all()
    observations = db.query(Observation).all()
    logs = db.query(ResolutionLog).order_by(ResolutionLog.created_at.desc()).limit(200).all()

    total_obs = len(observations)
    failed_obs = sum(1 for o in observations if o.status == "failed")
    avg_obs_ms = round(sum(o.duration_ms for o in observations) / total_obs, 2) if total_obs else 0.0

    latencies = [log.latency_ms for log in logs]
    avg_runtime_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "atlas": {
            "total_runs": len(runs),
            "total_observations": total_obs,
            "distinct_behaviours": db.query(Behaviour).count(),
            "failure_rate": round(failed_obs / total_obs, 4) if total_obs else 0.0,
            "avg_observation_duration_ms": avg_obs_ms,
        },
        "runtime": {
            "total_resolutions": len(logs),
            "avg_latency_ms": avg_runtime_ms,
            "measured_samples": len(latencies),
        },
    }
