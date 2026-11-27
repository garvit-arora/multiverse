"""SQLAlchemy ORM models for Multiverse (MySQL 8 & SQLite compatible)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    passports: Mapped[list["Passport"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), default="owner", nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), default="build-0.1.0", nullable=False)
    flagsmith_api_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    flagsmith_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="applications")
    environments: Mapped[list["Environment"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    capabilities: Mapped[list["Capability"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    workflows: Mapped[list["Workflow"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    behaviours: Mapped[list["Behaviour"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), default="sandbox", nullable=False)
    flagsmith_environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_ref: Mapped[str] = mapped_column(Text, default="", nullable=False)  # encrypted token/key
    type: Mapped[str] = mapped_column(String(32), default="sandbox", nullable=False)  # baseline | sandbox | production

    application: Mapped["Application"] = relationship(back_populates="environments")
    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="environment", cascade="all, delete-orphan")
    exploration_runs: Mapped[list["ExplorationRun"]] = relationship(back_populates="environment", cascade="all, delete-orphan")
    branches: Mapped[list["Branch"]] = relationship(back_populates="environment", cascade="all, delete-orphan")


class Capability(Base):
    __tablename__ = "capabilities"
    __table_args__ = (
        UniqueConstraint("application_id", "semantic_key", name="uq_app_semantic_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    semantic_key: Mapped[str] = mapped_column(String(128), nullable=False)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="capabilities")


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="workflows")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    environment: Mapped["Environment"] = relationship(back_populates="snapshots")
    configurations: Mapped[list["Configuration"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class Configuration(Base):
    __tablename__ = "configurations"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "configuration_hash", name="uq_snapshot_config_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assignments_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    identity_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    snapshot: Mapped["Snapshot"] = relationship(back_populates="configurations")


class ExplorationRun(Base):
    __tablename__ = "exploration_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), default="adaptive", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    budget: Mapped[int] = mapped_column(Integer, default=64, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    environment: Mapped["Environment"] = relationship(back_populates="exploration_runs")
    observations: Mapped[list["Observation"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Behaviour(Base):
    __tablename__ = "behaviours"
    __table_args__ = (
        UniqueConstraint("application_id", "workflow_version", "fingerprint", name="uq_app_wf_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    representative_config_id: Mapped[str | None] = mapped_column(ForeignKey("configurations.id", ondelete="SET NULL"), nullable=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    stability_status: Mapped[str] = mapped_column(String(32), default="stable", nullable=False)

    application: Mapped["Application"] = relationship(back_populates="behaviours")


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("exploration_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False)
    behaviour_id: Mapped[str | None] = mapped_column(ForeignKey("behaviours.id", ondelete="SET NULL"), nullable=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)  # success | failed | unstable
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    run: Mapped["ExplorationRun"] = relationship(back_populates="observations")


class BehaviourEdge(Base):
    __tablename__ = "behaviour_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    from_behaviour_id: Mapped[str] = mapped_column(ForeignKey("behaviours.id", ondelete="CASCADE"), nullable=False, index=True)
    to_behaviour_id: Mapped[str] = mapped_column(ForeignKey("behaviours.id", ondelete="CASCADE"), nullable=False, index=True)
    source_observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id", ondelete="SET NULL"), nullable=True)
    target_observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id", ondelete="SET NULL"), nullable=True)
    flag_delta_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), default="observed_delta", nullable=False)


class Commit(Base):
    __tablename__ = "commits"

    commit_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), default="build-0.1.0", nullable=False)
    evidence_behaviour_id: Mapped[str | None] = mapped_column(ForeignKey("behaviours.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CommitParent(Base):
    __tablename__ = "commit_parents"

    commit_hash: Mapped[str] = mapped_column(ForeignKey("commits.commit_hash", ondelete="CASCADE"), primary_key=True)
    parent_hash: Mapped[str] = mapped_column(ForeignKey("commits.commit_hash", ondelete="CASCADE"), primary_key=True)
    parent_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("environment_id", "name", name="uq_env_branch_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    head_commit_hash: Mapped[str] = mapped_column(ForeignKey("commits.commit_hash", ondelete="RESTRICT"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    environment: Mapped["Environment"] = relationship(back_populates="branches")


class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    commit_hash: Mapped[str] = mapped_column(ForeignKey("commits.commit_hash", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Passport(Base):
    __tablename__ = "passports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="passports")
    preferences: Mapped[list["Preference"]] = relationship(back_populates="passport", cascade="all, delete-orphan")


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    passport_id: Mapped[str] = mapped_column(ForeignKey("passports.id", ondelete="CASCADE"), nullable=False, index=True)
    semantic_key: Mapped[str] = mapped_column(String(128), nullable=False)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)

    passport: Mapped["Passport"] = relationship(back_populates="preferences")


class ResolutionLog(Base):
    __tablename__ = "resolution_logs"
    __table_args__ = (
        Index("ix_resolution_app_created", "application_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    passport_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_revision: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    resolved_flags_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
