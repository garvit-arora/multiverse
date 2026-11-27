"""Background exploration execution engine (runs in RQ worker or background thread)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from services.api.atlas.explorer import (
    AdaptiveExplorer,
    ExplorationConstraints,
    canonical_config_hash,
    compute_finite_space_size,
    generate_exhaustive,
    generate_pairwise,
    measure_pairwise_coverage,
)
from services.api.core.database import SessionLocal
from services.api.models.schema import (
    Application,
    Behaviour,
    BehaviourEdge,
    Configuration,
    Environment,
    ExplorationRun,
    Observation,
    Snapshot,
    Workflow,
)
from services.worker.browser.runner import execute_workflow_observation


def run_exploration_job(
    run_id: str,
    domains: dict[str, list[Any]],
    constraints_dict: dict[str, Any] | None = None,
) -> None:
    """Execute an Atlas exploration run against the registered application and persist all results."""
    db: Session = SessionLocal()
    try:
        run = db.get(ExplorationRun, run_id)
        if not run or run.status == "cancelled":
            return

        env = db.get(Environment, run.environment_id)
        wf = db.get(Workflow, run.workflow_id)
        app = db.get(Application, env.application_id) if env else None
        if not env or not wf or not app:
            if run:
                run.status = "failed"
                run.metrics_json = {"error": "Missing environment, workflow, or application"}
                db.commit()
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        constraints = ExplorationConstraints(
            forbidden_pairs=(constraints_dict or {}).get("forbidden_pairs", []),
            requires=(constraints_dict or {}).get("requires", []),
        )

        # Ensure a snapshot exists for this exploration
        snapshot = (
            db.query(Snapshot)
            .filter(Snapshot.environment_id == env.id)
            .order_by(Snapshot.captured_at.desc())
            .first()
        )
        if not snapshot:
            snapshot = Snapshot(
                environment_id=env.id,
                document_hash=canonical_config_hash({"env": env.id, "domains": domains}),
                document_json={"domains": domains},
            )
            db.add(snapshot)
            db.commit()

        # Select strategy
        strategy = run.strategy
        budget = run.budget
        adaptive: AdaptiveExplorer | None = None
        candidates: list[dict[str, Any]] = []

        if strategy == "exhaustive":
            candidates = generate_exhaustive(domains, constraints, limit=budget)
        elif strategy == "pairwise":
            candidates, _ = generate_pairwise(domains, constraints, budget=budget)
        else:
            adaptive = AdaptiveExplorer(domains, constraints=constraints, seed=run.seed)

        seen_behaviours: dict[str, Behaviour] = {
            b.fingerprint: b
            for b in db.query(Behaviour)
            .filter(Behaviour.application_id == app.id, Behaviour.workflow_version == wf.version)
            .all()
        }
        executed_configs: list[dict[str, Any]] = []
        previous_behaviour_id: str | None = None
        previous_obs_id: str | None = None
        previous_cfg: dict[str, Any] | None = None
        failures = 0
        idx = 0

        while idx < budget:
            db.refresh(run)
            if run.status == "cancelled":
                break

            if adaptive is not None:
                if not adaptive.has_next():
                    break
                cfg = adaptive.next_candidate()
                if cfg is None:
                    break
            else:
                if idx >= len(candidates):
                    break
                cfg = candidates[idx]

            cfg_hash = canonical_config_hash(cfg)
            cfg_rec = (
                db.query(Configuration)
                .filter(Configuration.snapshot_id == snapshot.id, Configuration.configuration_hash == cfg_hash)
                .first()
            )
            if not cfg_rec:
                cfg_rec = Configuration(
                    snapshot_id=snapshot.id,
                    configuration_hash=cfg_hash,
                    assignments_json=cfg,
                    identity_context_json={"synthetic_index": idx, "run_id": run.id},
                )
                db.add(cfg_rec)
                db.flush()

            obs_res = execute_workflow_observation(
                base_url=app.base_url,
                workflow_def=wf.definition_json,
                config_assignments=cfg,
                run_id=run.id,
                candidate_index=idx,
            )

            fp = obs_res["fingerprint"]
            is_novel = fp not in seen_behaviours
            if obs_res["status"] == "failed":
                failures += 1

            behaviour = seen_behaviours.get(fp)
            if not behaviour and obs_res["status"] == "success":
                behaviour = Behaviour(
                    application_id=app.id,
                    workflow_version=wf.version,
                    fingerprint=fp,
                    representative_config_id=cfg_rec.id,
                    summary_json=obs_res["normalized"],
                    stability_status="stable",
                )
                db.add(behaviour)
                db.flush()
                seen_behaviours[fp] = behaviour

            obs_rec = Observation(
                run_id=run.id,
                configuration_id=cfg_rec.id,
                behaviour_id=behaviour.id if behaviour else None,
                fingerprint=fp,
                status=obs_res["status"],
                artifact_path=obs_res.get("artifact_path"),
                duration_ms=obs_res["duration_ms"],
                evidence_json={
                    "normalized": obs_res["normalized"],
                    "error": obs_res.get("error"),
                    "assignments": cfg,
                },
            )
            db.add(obs_rec)
            db.flush()

            if behaviour and previous_behaviour_id and behaviour.id != previous_behaviour_id and previous_cfg:
                delta = {
                    k: {"from": previous_cfg.get(k), "to": cfg.get(k)}
                    for k in set(cfg) | set(previous_cfg)
                    if previous_cfg.get(k) != cfg.get(k)
                }
                db.add(
                    BehaviourEdge(
                        from_behaviour_id=previous_behaviour_id,
                        to_behaviour_id=behaviour.id,
                        source_observation_id=previous_obs_id,
                        target_observation_id=obs_rec.id,
                        flag_delta_json=delta,
                        relationship_type="observed_delta",
                    )
                )

            if behaviour:
                previous_behaviour_id = behaviour.id
                previous_obs_id = obs_rec.id
                previous_cfg = cfg

            if adaptive is not None:
                adaptive.record_observation(cfg, fp, is_novel)

            executed_configs.append(cfg)
            idx += 1

            total_space = compute_finite_space_size(domains)
            pw_cov = measure_pairwise_coverage(executed_configs, domains)
            run.metrics_json = {
                "executed_count": idx,
                "budget": budget,
                "distinct_behaviours": len(seen_behaviours),
                "failures": failures,
                "total_finite_space": total_space,
                "configuration_coverage": round(idx / max(total_space, 1), 4),
                "pairwise_coverage": round(pw_cov, 4),
                "compression_ratio": round(idx / max(len(seen_behaviours), 1), 2),
                "last_fingerprint": fp,
            }
            db.commit()

        db.refresh(run)
        if run.status != "cancelled":
            run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
