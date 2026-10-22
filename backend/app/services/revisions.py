"""Workpaper revisions: an engine version plus approved adjustments, with an estimated summary.

`WP` is the live working revision (base + every approved, unreversed adjustment). `R1`, `R2`... are frozen
snapshots (created explicitly, at client approval, or at filing). Engine versions v1..v3 are untouched.
"""

from __future__ import annotations

import copy
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import Adjustment, ReturnVersion, WorkpaperRevision
from app.services.context import get_index

WORKING = "WP"


def active_base_version(db: Session) -> str:
    return get_index(db).current_version


def approved_adjustments(db: Session, base: str) -> list[Adjustment]:
    return list(db.scalars(select(Adjustment).where(
        Adjustment.base_version == base, Adjustment.status == "approved", Adjustment.reverses_id.is_(None)
    ).order_by(Adjustment.decided_at, Adjustment.id)).all())


def estimated_summary(base_summary: dict, adjustments: list[Adjustment]) -> dict:
    from app.services.tax_effects import estimate

    s = copy.deepcopy(base_summary)
    fed_tax = fed_pay = ca_tax = ca_pay = 0.0
    for a in adjustments:
        e = estimate(_rates(a.base_version), a.tax_category, a.delta)
        fed_tax += float(e["fed_tax"])
        fed_pay += float(e["fed_payments"])
        ca_tax += float(e["ca_tax"])
        ca_pay += float(e["ca_payments"])
    f, c = s["federal"], s["california"]
    f["total_tax"] = round(f["total_tax"] + fed_tax)
    f["payments"] = round(f["payments"] + fed_pay)
    f["balance_due"] = round(f["total_tax"] - f["payments"])
    c["total_tax"] = round(c["total_tax"] + ca_tax)
    c["payments"] = round(c["payments"] + ca_pay)
    c["balance_due"] = round(c["total_tax"] - c["payments"])
    s["estimated"] = bool(adjustments)
    s["adjustment_count"] = len(adjustments)
    s["delta"] = {"federal_tax": round(fed_tax, 2), "federal_payments": round(fed_pay, 2),
                  "california_tax": round(ca_tax, 2), "california_payments": round(ca_pay, 2)}
    return s


_RATES: dict[str, dict] = {}


def _rates(version: str) -> dict:
    return _RATES.get(version, {})


def load_rates(db: Session) -> None:
    for v in db.scalars(select(ReturnVersion)).all():
        _RATES[v.version] = v.tax_effect_rates


def working_state(db: Session) -> dict:
    load_rates(db)
    idx = get_index(db)
    base = active_base_version(db)
    adjs = approved_adjustments(db, base)
    overrides: dict[str, float] = {}
    for a in adjs:
        cur = overrides.get(a.line_key, float(a.original_value))
        overrides[a.line_key] = round(cur + float(a.delta), 2)
    summary = estimated_summary(idx.versions[base]["summary"], adjs)
    return {"label": WORKING, "kind": "working", "base_version": base, "adjustment_ids": [a.id for a in adjs],
            "overrides": overrides, "summary": summary, "fingerprint": fingerprint(base, overrides)}


def fingerprint(base: str, overrides: dict) -> str:
    payload = json.dumps({"base": base, "overrides": overrides}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def revision_lines(db: Session, label: str) -> dict:
    idx = get_index(db)
    if label in idx.versions:
        v = idx.versions[label]
        return {"label": label, "kind": "engine", "base_version": label, "summary": v["summary"],
                "computed_at": v["computed_at"],
                "lines": {k: {"label": ln["label"], "value": ln["value"]} for k, ln in idx.lines[label].items()}}
    if label == WORKING:
        st = working_state(db)
        overrides, base, summary = st["overrides"], st["base_version"], st["summary"]
        meta = {"label": WORKING, "kind": "working", "base_version": base, "summary": summary}
    else:
        rev = db.scalar(select(WorkpaperRevision).where(WorkpaperRevision.label == label))
        if not rev:
            raise NotFound(f"Revision {label} not found")
        overrides, base = rev.lines, rev.base_version
        meta = {"label": rev.label, "kind": rev.kind, "base_version": base, "summary": rev.summary,
                "computed_at": rev.created_at, "description": rev.description}
    lines = {}
    for k, ln in idx.lines[base].items():
        if k in overrides:
            lines[k] = {"label": ln["label"], "value": overrides[k], "adjusted": True, "base_value": ln["value"]}
        else:
            lines[k] = {"label": ln["label"], "value": ln["value"]}
    return {**meta, "lines": lines}


def list_revisions(db: Session) -> list[dict]:
    st = working_state(db)
    rows = db.scalars(select(WorkpaperRevision).order_by(WorkpaperRevision.id)).all()
    return [
        {"label": WORKING, "kind": "working", "base_version": st["base_version"], "summary": st["summary"],
         "adjustment_ids": st["adjustment_ids"], "fingerprint": st["fingerprint"],
         "description": "Live working revision: base version plus every approved adjustment"},
        *[{"label": r.label, "kind": r.kind, "base_version": r.base_version, "summary": r.summary,
           "adjustment_ids": r.adjustment_ids, "fingerprint": r.fingerprint, "description": r.description,
           "created_at": r.created_at, "created_by": r.created_by, "parent_id": r.parent_id} for r in rows],
    ]


def freeze_revision(db: Session, actor_id: str, description: str, kind: str = "working",
                    parent_id: int | None = None) -> WorkpaperRevision:
    st = working_state(db)
    n = len(db.scalars(select(WorkpaperRevision.id)).all()) + 1
    rev = WorkpaperRevision(label=f"R{n}", base_version=st["base_version"], kind=kind, description=description,
                            adjustment_ids=st["adjustment_ids"], lines=st["overrides"], summary=st["summary"],
                            fingerprint=st["fingerprint"], parent_id=parent_id, created_by=actor_id)
    db.add(rev)
    db.flush()
    return rev
