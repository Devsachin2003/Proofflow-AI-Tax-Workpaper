"""Persist independent validation findings without changing return lines or reopening human decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid, NotFound
from app.core.masking import mask_deep, mask_text
from app.core.permissions import require
from app.models import AuditEvent, Comment, Finding
from app.services import audit
from app.services.context import get_index
from app.services.revisions import active_base_version
from app.services.tax_effects import estimate
from app.validation.rules import run_rules

_PRESERVE = {"resolved", "false_positive", "accepted"}
_DECISIONS = {"open", "in_review", "resolved", "false_positive", "accepted"}


def run_validation(db: Session, actor_id: str | None = None) -> dict:
    idx = get_index(db)
    version = active_base_version(db)
    rates = idx.versions[version]["tax_effect_rates"]
    drafts = run_rules(idx, version)
    existing = {f.fingerprint: f for f in db.scalars(select(Finding)).all()}
    seen: set[str] = set()
    created = updated = preserved = 0
    now = datetime.now(UTC)
    for draft in drafts:
        seen.add(draft.fingerprint)
        fed, ca, basis = _effects(rates, draft)
        row = existing.get(draft.fingerprint)
        if row is None:
            db.add(Finding(
                id=draft.id,
                rule_id=draft.rule_id,
                fingerprint=draft.fingerprint,
                title=draft.title,
                description=draft.description,
                category=draft.category,
                severity=draft.severity,
                blocks_filing=draft.blocks_filing,
                area_id=draft.area_id,
                base_version=version,
                affected_amount=_money(draft.affected_amount),
                fed_effect=fed,
                ca_effect=ca,
                effect_basis=basis,
                evidence=draft.evidence,
                line_keys=draft.line_keys,
                details=draft.details,
                recommended_action=draft.recommended_action,
                proposed_adjustments=[],
                confidence=draft.confidence,
                status="open",
                detected_at=now,
                last_detected_at=now,
                still_detected=True,
                row_version=1,
            ))
            created += 1
            continue
        row.title = draft.title
        row.description = draft.description
        row.category = draft.category
        row.severity = draft.severity
        row.blocks_filing = draft.blocks_filing
        row.area_id = draft.area_id
        row.base_version = version
        row.affected_amount = _money(draft.affected_amount)
        row.fed_effect = fed
        row.ca_effect = ca
        row.effect_basis = basis
        row.evidence = draft.evidence
        row.line_keys = draft.line_keys
        row.details = draft.details
        row.recommended_action = draft.recommended_action
        row.confidence = draft.confidence
        row.last_detected_at = now
        row.still_detected = True
        if row.status in _PRESERVE:
            preserved += 1
        updated += 1
    for fp, row in existing.items():
        if fp not in seen and row.still_detected:
            row.still_detected = False
    audit.record(
        db, actor=_actor(actor_id), action="validation.run", entity_type="finding", entity_id="scan",
        summary=f"Validation on {version}: {created} new, {updated} refreshed, {preserved} human decisions kept",
        after={"created": created, "updated": updated, "preserved": preserved, "detected": len(drafts)},
    )
    db.commit()
    return {
        "status": "ok",
        "base_version": version,
        "detected": len(drafts),
        "created": created,
        "updated": updated,
        "preserved": preserved,
        "findings": _count(db),
        "actor_id": actor_id,
    }


class _Actor:
    def __init__(self, actor_id: str | None):
        self.id = actor_id or "system"
        self.role = "system"


def _actor(actor_id: str | None) -> _Actor:
    return _Actor(actor_id)


def _effects(rates: dict, draft) -> tuple[Decimal | None, Decimal | None, str | None]:
    if draft.tax_delta is None or not draft.tax_category:
        return None, None, None
    est = estimate(rates, draft.tax_category, draft.tax_delta)
    note = est["note"] + " Estimate only; the return was not recomputed."
    return est["fed_effect"], est["ca_effect"], note


def _money(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(value, 2)))


def _count(db: Session) -> int:
    from sqlalchemy import func

    return db.scalar(select(func.count()).select_from(Finding)) or 0


def _brief(f: Finding) -> dict:
    return {
        "id": f.id, "rule_id": f.rule_id, "title": f.title,
        "category": f.category, "severity": f.severity, "status": f.status,
        "blocks_filing": f.blocks_filing, "affected_amount": _num(f.affected_amount),
        "fed_effect": _num(f.fed_effect), "ca_effect": _num(f.ca_effect),
        "effect_basis": f.effect_basis, "evidence": f.evidence or [], "line_keys": f.line_keys or [],
        "description": mask_text(f.description),
        "recommended_action": f.recommended_action, "assignee_id": f.assignee_id,
        "area_id": f.area_id, "confidence": f.confidence, "still_detected": f.still_detected,
        "base_version": f.base_version, "row_version": f.row_version,
    }


def _num(value) -> float | None:
    return None if value is None else float(value)


def list_findings(db: Session, status: str | None = None) -> dict:
    stmt = select(Finding)
    if status:
        stmt = stmt.where(Finding.status == status)
    rows = list(db.scalars(stmt).all())
    rank = {"error": 0, "warning": 1, "info": 2}
    rows.sort(key=lambda f: (rank.get(f.severity, 9), -(float(f.affected_amount or 0)), f.id))
    return {"total": len(rows), "items": [_brief(f) for f in rows], "engine_pending": False}


def get_finding(db: Session, finding_id: str) -> dict:
    row = db.get(Finding, finding_id)
    if row is None:
        raise NotFound(f"Finding {finding_id} not found")
    notes = db.scalars(select(Comment).where(
        Comment.target_type == "finding", Comment.target_id == finding_id
    ).order_by(Comment.created_at)).all()
    history = db.scalars(select(AuditEvent).where(
        AuditEvent.entity_type == "finding", AuditEvent.entity_id == finding_id
    ).order_by(AuditEvent.id)).all()
    return {
        **_brief(row),
        "details": mask_deep(row.details or {}),
        "resolution_note": row.resolution_note,
        "resolved_by": row.resolved_by,
        "resolved_at": row.resolved_at,
        "detected_at": row.detected_at,
        "last_detected_at": row.last_detected_at,
        "notes": [{"id": n.id, "author_id": n.author_id, "body": n.body, "created_at": n.created_at, "kind": n.kind}
                  for n in notes],
        "audit": [{"id": e.id, "at": e.at, "actor_id": e.actor_id, "actor_role": e.actor_role,
                   "action": e.action, "summary": e.summary, "before": e.before, "after": e.after}
                  for e in history],
    }


def decide_finding(db: Session, user, finding_id: str, status: str, note: str | None,
                   expected_version: int | None = None) -> dict:
    if status not in _DECISIONS:
        raise Invalid(f"Status must be one of {sorted(_DECISIONS)}")
    require(user, "finding.false_positive" if status == "false_positive" else "finding.update")
    row = db.get(Finding, finding_id)
    if row is None:
        raise NotFound(f"Finding {finding_id} not found")
    if expected_version is not None and row.row_version != expected_version:
        raise Conflict("Finding was updated by someone else.", details={"row_version": row.row_version})
    if status in {"resolved", "false_positive", "accepted"} and not (note and note.strip()):
        raise Invalid("A note is required when verifying or dismissing a finding.")
    before = {"status": row.status, "resolution_note": row.resolution_note}
    row.status = status
    row.row_version += 1
    if note and note.strip():
        row.resolution_note = note.strip()
        db.add(Comment(target_type="finding", target_id=row.id, kind="internal", body=note.strip(),
                       author_id=user.id))
    if status in _PRESERVE:
        row.resolved_by = user.id
        row.resolved_at = datetime.now(UTC)
    else:
        row.resolved_by = None
        row.resolved_at = None
    audit.record(
        db, actor=user, action="finding.decide", entity_type="finding", entity_id=row.id,
        summary=f"{row.id} marked {status}", before=before,
        after={"status": row.status, "resolution_note": row.resolution_note}, reason=note,
    )
    db.commit()
    return get_finding(db, row.id)
