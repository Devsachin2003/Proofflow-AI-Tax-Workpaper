"""Workpaper tables: the system of record for human review work, layered over the immutable baseline."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

Money = Numeric(18, 2)


class WorkpaperArea(Base):
    __tablename__ = "workpaper_area"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    group: Mapped[str] = mapped_column(String(64))
    line_prefixes: Mapped[list[str]] = mapped_column(ARRAY(String))
    budget_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="not_started")
    preparer_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class Finding(Base):
    __tablename__ = "finding"
    __table_args__ = (
        CheckConstraint(
            "category in ('confirmed_error','suspected_discrepancy','needs_judgment','informational')",
            name="ck_finding_category",
        ),
        CheckConstraint(
            "status in ('open','in_review','resolved','false_positive','accepted')", name="ck_finding_status"
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(48), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    blocks_filing: Mapped[bool] = mapped_column(Boolean, default=False)
    area_id: Mapped[str | None] = mapped_column(ForeignKey("workpaper_area.id"))
    base_version: Mapped[str] = mapped_column(String(8))
    affected_amount: Mapped[Decimal | None] = mapped_column(Money)
    fed_effect: Mapped[Decimal | None] = mapped_column(Money)
    ca_effect: Mapped[Decimal | None] = mapped_column(Money)
    effect_basis: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    line_keys: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    recommended_action: Mapped[str] = mapped_column(Text)
    proposed_adjustments: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[str] = mapped_column(String(16))  # deterministic | heuristic
    status: Mapped[str] = mapped_column(String(16), default="open")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(16))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    still_detected: Mapped[bool] = mapped_column(Boolean, default=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class Verification(Base):
    __tablename__ = "verification"
    __table_args__ = (Index("ix_verification_target", "target_type", "target_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16))  # line | ev | document
    target_id: Mapped[str] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(8))
    method: Mapped[str] = mapped_column(String(48))
    note: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)


class Adjustment(Base):
    __tablename__ = "adjustment"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','submitted','approved','rejected','reversed','withdrawn')", name="ck_adj_status"
        ),
    )
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    base_version: Mapped[str] = mapped_column(String(8))
    line_key: Mapped[str] = mapped_column(String(64), index=True)
    line_label: Mapped[str] = mapped_column(Text)
    original_value: Mapped[Decimal] = mapped_column(Money)
    proposed_value: Mapped[Decimal] = mapped_column(Money)
    delta: Mapped[Decimal] = mapped_column(Money)
    tax_category: Mapped[str] = mapped_column(String(32))
    fed_effect: Mapped[Decimal] = mapped_column(Money)
    ca_effect: Mapped[Decimal] = mapped_column(Money)
    effect_note: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("finding.id"))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    requires_partner: Mapped[bool] = mapped_column(Boolean, default=False)
    prepared_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(16))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    reverses_id: Mapped[str | None] = mapped_column(String(16))
    reversed_by_id: Mapped[str | None] = mapped_column(String(16))
    batch_id: Mapped[str | None] = mapped_column(String(32))
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class WorkpaperRevision(Base):
    __tablename__ = "workpaper_revision"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(16), unique=True)
    base_version: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(16), default="working")  # working | filed | amendment
    description: Mapped[str] = mapped_column(Text)
    adjustment_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    lines: Mapped[dict] = mapped_column(JSONB, default=dict)  # {key: value} overrides vs base
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("workpaper_revision.id"))
    created_by: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewNote(Base):
    __tablename__ = "review_note"
    __table_args__ = (
        CheckConstraint(
            "kind in ('review_note','judgment_call','election','due_diligence','penalty_decision')",
            name="ck_note_kind",
        ),
        CheckConstraint("status in ('open','responded','cleared')", name="ck_note_status"),
        CheckConstraint(
            "kind = 'review_note' or authority is not null", name="ck_judgment_requires_authority"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), default="review_note")
    target_type: Mapped[str | None] = mapped_column(String(16))
    target_id: Mapped[str | None] = mapped_column(String(128))
    area_id: Mapped[str | None] = mapped_column(ForeignKey("workpaper_area.id"))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    authority: Mapped[str | None] = mapped_column(Text)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    response: Mapped[str | None] = mapped_column(Text)
    responded_by: Mapped[str | None] = mapped_column(String(16))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_by: Mapped[str | None] = mapped_column(String(16))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class Comment(Base):
    __tablename__ = "comment"
    __table_args__ = (Index("ix_comment_target", "target_type", "target_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(24), default="internal")  # internal | client_question | answer
    body: Mapped[str] = mapped_column(Text)
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    addressed_to: Mapped[str | None] = mapped_column(String(16))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comment.id"))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | answered | closed
    evidence_document_id: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assignment(Base):
    __tablename__ = "assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    area_id: Mapped[str | None] = mapped_column(ForeignKey("workpaper_area.id"))
    target_type: Mapped[str | None] = mapped_column(String(16))
    target_id: Mapped[str | None] = mapped_column(String(128))
    assignee_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    role: Mapped[str] = mapped_column(String(32))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | done
    created_by: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signoff(Base):
    __tablename__ = "signoff"
    __table_args__ = (Index("ix_signoff_scope", "scope_type", "scope_id", "status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(16))  # area | return
    scope_id: Mapped[str] = mapped_column(String(48))
    level: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fingerprint: Mapped[str] = mapped_column(String(64))
    revision_label: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | invalidated
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_reason: Mapped[str | None] = mapped_column(Text)


class FilingRecord(Base):
    __tablename__ = "filing_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))  # extension | original | amendment
    status: Mapped[str] = mapped_column(String(24))  # submitted | rejected | accepted | not_transmitted
    revision_label: Mapped[str | None] = mapped_column(String(16))
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    submission_id: Mapped[str | None] = mapped_column(String(32))
    errors: Mapped[list] = mapped_column(JSONB, default=list)
    amount: Mapped[Decimal | None] = mapped_column(Money)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("filing_record.id"))
    source: Mapped[str] = mapped_column(String(16), default="workpaper")  # workpaper | replay
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimeEntry(Base):
    __tablename__ = "time_entry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    budget_key: Mapped[str] = mapped_column(String(64))
    hours: Mapped[float] = mapped_column(Float)
    work_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FirmSetting(Base):
    __tablename__ = "firm_setting"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | int | float | str] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str | None] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    """Append-only. A database trigger (see the initial migration) rejects UPDATE and DELETE."""

    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[str | None] = mapped_column(String(16))
    actor_role: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    simulated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SensitiveAccessLog(Base):
    __tablename__ = "sensitive_access_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[str] = mapped_column(String(16))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    field: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    granted: Mapped[bool] = mapped_column(Boolean)


class Notification(Base):
    __tablename__ = "notification"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSeen(Base):
    __tablename__ = "user_seen"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    last_audit_id: Mapped[int] = mapped_column(BigInteger, default=0)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReplayState(Base):
    __tablename__ = "replay_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    now: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    applied_event_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class AiResponse(Base):
    __tablename__ = "ai_response"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[str] = mapped_column(String(16))
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSONB)
    answer: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(64))
    grounded: Mapped[bool] = mapped_column(Boolean)
