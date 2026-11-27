"""Verse behavioural version control: immutable snapshots, commits, branches, 3-way merge, and preview links."""
from __future__ import annotations

import hashlib
import secrets
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import rfc8785
from sqlalchemy.orm import Session

from services.api.core.security import sha256_hex
from services.api.models.schema import (
    Branch,
    Commit,
    CommitParent,
    Configuration,
    ShareLink,
    Snapshot,
)


class ConcurrencyError(ValueError):
    """Raised when optimistic concurrency check fails on branch update."""


class MergeConflictError(ValueError):
    """Raised when a three-way merge has unresolved conflicts."""


@dataclass
class DiffResult:
    added: dict[str, Any]
    removed: dict[str, Any]
    changed: dict[str, dict[str, Any]]
    unchanged_count: int


def compute_commit_hash(
    configuration_hash: str,
    parent_hashes: list[str],
    author_id: str,
    message: str,
    build_id: str,
    created_at_iso: str,
) -> str:
    payload = {
        "configuration_hash": configuration_hash,
        "parent_hashes": parent_hashes,
        "author_id": author_id,
        "message": message,
        "build_id": build_id,
        "created_at": created_at_iso,
    }
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


def diff_configurations(base: dict[str, Any], target: dict[str, Any]) -> DiffResult:
    added = {k: target[k] for k in target if k not in base}
    removed = {k: base[k] for k in base if k not in target}
    changed: dict[str, dict[str, Any]] = {}
    unchanged = 0
    for k in base:
        if k in target:
            if base[k] != target[k]:
                changed[k] = {"from": base[k], "to": target[k]}
            else:
                unchanged += 1
    return DiffResult(added=added, removed=removed, changed=changed, unchanged_count=unchanged)


def three_way_merge(
    ancestor: dict[str, Any],
    source: dict[str, Any],
    destination: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Perform a deterministic 3-way merge over configuration key-value assignments."""
    all_keys = sorted(set(ancestor.keys()) | set(source.keys()) | set(destination.keys()))
    merged: dict[str, Any] = {}
    conflicts: list[dict[str, Any]] = []

    for k in all_keys:
        in_a = k in ancestor
        in_s = k in source
        in_d = k in destination
        va = ancestor.get(k)
        vs = source.get(k)
        vd = destination.get(k)

        if in_s == in_d and vs == vd:
            if in_s:
                merged[k] = vs
        elif in_s == in_a and vs == va:
            # Only destination changed
            if in_d:
                merged[k] = vd
        elif in_d == in_a and vd == va:
            # Only source changed
            if in_s:
                merged[k] = vs
        else:
            # Both changed differently -> conflict
            conflicts.append({
                "key": k,
                "ancestor": va if in_a else None,
                "source": vs if in_s else None,
                "destination": vd if in_d else None,
            })

    return merged, conflicts


def find_common_ancestor(db: Session, commit_a: str, commit_b: str) -> str | None:
    """Find lowest common ancestor commit hash using BFS over commit_parents DAG."""
    if commit_a == commit_b:
        return commit_a

    def ancestors_of(start: str) -> dict[str, int]:
        dist: dict[str, int] = {start: 0}
        q = deque([start])
        while q:
            curr = q.popleft()
            parents = db.query(CommitParent).filter(CommitParent.commit_hash == curr).all()
            for p in parents:
                if p.parent_hash not in dist:
                    dist[p.parent_hash] = dist[curr] + 1
                    q.append(p.parent_hash)
        return dist

    anc_a = ancestors_of(commit_a)
    anc_b = ancestors_of(commit_b)
    common = set(anc_a.keys()) & set(anc_b.keys())
    if not common:
        return None
    return min(common, key=lambda c: anc_a[c] + anc_b[c])


def create_commit_record(
    db: Session,
    environment_id: str,
    assignments: dict[str, Any],
    author_id: str,
    message: str,
    parent_hashes: list[str] | None = None,
    build_id: str = "build-0.1.0",
    evidence_behaviour_id: str | None = None,
) -> Commit:
    parent_hashes = parent_hashes or []
    now = datetime.now(timezone.utc)
    doc_hash = hashlib.sha256(rfc8785.dumps(assignments)).hexdigest()

    snapshot = db.query(Snapshot).filter(
        Snapshot.environment_id == environment_id,
        Snapshot.document_hash == doc_hash,
    ).first()
    if not snapshot:
        snapshot = Snapshot(
            environment_id=environment_id,
            document_hash=doc_hash,
            document_json={"assignments": assignments},
            captured_at=now,
        )
        db.add(snapshot)
        db.flush()

    cfg = db.query(Configuration).filter(
        Configuration.snapshot_id == snapshot.id,
        Configuration.configuration_hash == doc_hash,
    ).first()
    if not cfg:
        cfg = Configuration(
            snapshot_id=snapshot.id,
            configuration_hash=doc_hash,
            assignments_json=assignments,
            identity_context_json={},
        )
        db.add(cfg)
        db.flush()

    commit_hash = compute_commit_hash(doc_hash, parent_hashes, author_id, message, build_id, now.isoformat())
    existing = db.get(Commit, commit_hash)
    if existing:
        return existing

    commit = Commit(
        commit_hash=commit_hash,
        configuration_id=cfg.id,
        author_id=author_id,
        message=message,
        build_id=build_id,
        evidence_behaviour_id=evidence_behaviour_id,
        created_at=now,
    )
    db.add(commit)
    db.flush()

    for idx, ph in enumerate(parent_hashes):
        db.add(CommitParent(commit_hash=commit_hash, parent_hash=ph, parent_order=idx))
    db.flush()
    return commit


def update_branch_head(db: Session, branch: Branch, new_commit_hash: str, expected_revision: int) -> Branch:
    """Update branch head with optimistic concurrency control."""
    if branch.revision != expected_revision:
        raise ConcurrencyError(
            f"Branch '{branch.name}' modified concurrently (expected rev {expected_revision}, actual {branch.revision})"
        )
    branch.head_commit_hash = new_commit_hash
    branch.revision += 1
    db.flush()
    return branch


def create_preview_share_link(
    db: Session,
    commit_hash: str,
    ttl_hours: int = 24,
) -> tuple[ShareLink, str]:
    """Generate an opaque preview token and store only its SHA-256 hash."""
    raw_token = f"mvp_{secrets.token_urlsafe(32)}"
    token_hash = sha256_hex(raw_token)
    link = ShareLink(
        commit_hash=commit_hash,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    db.add(link)
    db.flush()
    return link, raw_token
