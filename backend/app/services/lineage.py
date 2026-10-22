"""Calculation lineage: how any number was built, what it feeds, where it came from, and how it changed."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import any_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.core.masking import is_sensitive_field, mask_deep, mask_text, mask_value
from app.models import (
    Adjustment,
    Finding,
    LineInput,
    ReturnLine,
    ReturnVersion,
    ReviewNote,
    SourceRef,
    Verification,
    VersionChange,
    WorkpaperArea,
)
from app.services.context import get_index, get_resolver


def num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    return None


def area_for_key(db: Session, key: str) -> dict | None:
    for a in db.scalars(select(WorkpaperArea).order_by(WorkpaperArea.ordinal)).all():
        if any(re.search(p, key) for p in a.line_prefixes):
            return {"id": a.id, "title": a.title}
    return None


def areas_for_key(areas: list[WorkpaperArea], key: str) -> list[str]:
    return [a.id for a in areas if any(re.search(p, key) for p in a.line_prefixes)]


def versions(db: Session) -> list[dict]:
    rows = db.scalars(select(ReturnVersion).order_by(ReturnVersion.ordinal)).all()
    out = []
    for v in rows:
        n_lines = db.scalar(select(func.count()).select_from(ReturnLine).where(ReturnLine.version == v.version))
        out.append({
            "version": v.version, "computed_at": v.computed_at, "trigger": v.trigger, "summary": v.summary,
            "lines": n_lines, "documents_used": v.documents_used, "documents_superseded": v.documents_superseded,
            "tax_effect_rates": v.tax_effect_rates, "carryovers_out": v.carryovers_out,
        })
    return out


def list_lines(db: Session, version: str, q: str | None = None, form: str | None = None,
               jurisdiction: str | None = None, include_lots: bool = False, area: str | None = None,
               limit: int = 200, offset: int = 0) -> dict:
    stmt = select(ReturnLine).where(ReturnLine.version == version)
    if form:
        stmt = stmt.where(ReturnLine.form == form)
    if jurisdiction:
        stmt = stmt.where(ReturnLine.jurisdiction == jurisdiction)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(ReturnLine.key.ilike(like), ReturnLine.label.ilike(like)))
    if not include_lots and not form and not q:
        # lots are reached through their Form 8949 box totals; keep the default list readable
        stmt = stmt.where(~(ReturnLine.form == "F8949") | ReturnLine.key.ilike("%.total"))
    rows = db.scalars(stmt.order_by(ReturnLine.ordinal)).all()
    if area:
        a = db.get(WorkpaperArea, area)
        if a:
            rows = [r for r in rows if any(re.search(p, r.key) for p in a.line_prefixes)]
    total = len(rows)
    rows = rows[offset: offset + limit]
    keys = [r.key for r in rows]
    src_counts = dict(db.execute(
        select(SourceRef.owner_key, func.count()).where(
            SourceRef.owner_type == "line", SourceRef.version == version, SourceRef.owner_key.in_(keys)
        ).group_by(SourceRef.owner_key)
    ).all()) if keys else {}
    in_counts = dict(db.execute(
        select(LineInput.line_key, func.count()).where(LineInput.version == version, LineInput.line_key.in_(keys))
        .group_by(LineInput.line_key)
    ).all()) if keys else {}
    adj = effective_overrides(db, version)
    finding_keys = open_finding_line_keys(db)
    return {
        "total": total,
        "items": [
            {
                "key": r.key, "form": r.form, "line": r.line, "label": r.label, "jurisdiction": r.jurisdiction,
                "value": r.value, "rule": r.rule, "sources": src_counts.get(r.key, 0), "inputs": in_counts.get(r.key, 0),
                "effective_value": adj.get(r.key, {}).get("value"), "open_findings": finding_keys.get(r.key, 0),
            }
            for r in rows
        ],
    }


def open_finding_line_keys(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for keys in db.scalars(select(Finding.line_keys).where(Finding.status.in_(["open", "in_review"]))).all():
        for k in keys or []:
            counts[k] = counts.get(k, 0) + 1
    return counts


def effective_overrides(db: Session, version: str) -> dict[str, dict]:
    """Approved, unreversed adjustments on this base version: {line_key: {value, adjustments[]}}."""
    rows = db.scalars(
        select(Adjustment).where(Adjustment.base_version == version, Adjustment.status == "approved",
                                 Adjustment.reverses_id.is_(None)).order_by(Adjustment.decided_at)
    ).all()
    out: dict[str, dict] = {}
    for a in rows:
        cur = out.setdefault(a.line_key, {"value": float(a.original_value), "adjustments": []})
        cur["value"] = round(cur["value"] + float(a.delta), 2)
        cur["adjustments"].append(a.id)
    return out


def resolve_sources(db: Session, refs: list[SourceRef], version: str | None) -> list[dict]:
    idx = get_index(db)
    ev_ids = [r.target_id for r in refs if r.ref_type == "extracted_value" and r.target_id]
    verif = verification_map(db, "ev", ev_ids)
    out = []
    for r in refs:
        item: dict[str, Any] = {
            "ref": r.raw_ref, "type": r.ref_type, "resolved": r.resolved, "note": r.resolution_note,
            "document_id": r.document_id, "page": r.page, "target_id": r.target_id,
        }
        if r.ref_type == "extracted_value" and r.target_id in idx.ev:
            e = idx.ev[r.target_id]
            sensitive = is_sensitive_field(e["field"], e["value_type"])
            item.update({
                "label": e["label"], "field": e["field"], "value": mask_value(e["value_type"], e["value"]) if sensitive
                else e["value"], "value_type": e["value_type"], "text_as_read": mask_text(e["text_as_read"]),
                "confidence": e["confidence"], "position": e["position"],
                "document_title": idx.documents[e["document_id"]]["title"],
                "verification": verif.get(r.target_id),
            })
        else:
            res = get_resolver(db).resolve(r.raw_ref, version)
            item.update({"label": mask_text(res.label), "value": mask_deep(res.value)})
            if r.document_id and r.document_id in idx.documents:
                item["document_title"] = idx.documents[r.document_id]["title"]
        out.append(item)
    return out


def verification_map(db: Session, target_type: str, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    rows = db.scalars(select(Verification).where(
        Verification.target_type == target_type, Verification.target_id.in_(ids), Verification.superseded.is_(False)
    ).order_by(Verification.at)).all()
    return {v.target_id: {"method": v.method, "actor_id": v.actor_id, "at": v.at, "note": v.note} for v in rows}


def line_summary(r: ReturnLine, n_inputs: int = 0, n_sources: int = 0) -> dict:
    return {"key": r.key, "label": r.label, "value": r.value, "rule": r.rule, "form": r.form,
            "jurisdiction": r.jurisdiction, "inputs": n_inputs, "sources": n_sources}


def line_detail(db: Session, key: str, version: str) -> dict:
    idx = get_index(db)
    r = db.scalar(select(ReturnLine).where(ReturnLine.version == version, ReturnLine.key == key))
    if not r:
        raise NotFound(f"Line {key} not found in {version}")
    input_keys = [i.input_key for i in db.scalars(
        select(LineInput).where(LineInput.line_id == r.id).order_by(LineInput.position)).all()]
    input_rows = {x.key: x for x in db.scalars(
        select(ReturnLine).where(ReturnLine.version == version, ReturnLine.key.in_(input_keys))).all()}
    child_counts = dict(db.execute(
        select(LineInput.line_key, func.count()).where(LineInput.version == version,
                                                       LineInput.line_key.in_(input_keys))
        .group_by(LineInput.line_key)).all()) if input_keys else {}
    child_src = dict(db.execute(
        select(SourceRef.owner_key, func.count()).where(SourceRef.owner_type == "line", SourceRef.version == version,
                                                       SourceRef.owner_key.in_(input_keys))
        .group_by(SourceRef.owner_key)).all()) if input_keys else {}
    inputs = []
    for k in input_keys:
        x = input_rows.get(k)
        if x is None:
            inputs.append({"key": k, "label": None, "value": None, "resolved": False,
                           "note": f"Input line {k} is not present in {version}"})
        else:
            inputs.append({**line_summary(x, child_counts.get(k, 0), child_src.get(k, 0)), "resolved": True})

    consumer_keys = db.scalars(select(LineInput.line_key).where(
        LineInput.version == version, LineInput.input_key == key)).all()
    cons_inputs = dict(db.execute(
        select(LineInput.line_key, func.count()).where(LineInput.version == version,
                                                       LineInput.line_key.in_(consumer_keys))
        .group_by(LineInput.line_key)).all()) if consumer_keys else {}
    cons_src = dict(db.execute(
        select(SourceRef.owner_key, func.count()).where(SourceRef.owner_type == "line", SourceRef.version == version,
                                                       SourceRef.owner_key.in_(consumer_keys))
        .group_by(SourceRef.owner_key)).all()) if consumer_keys else {}
    consumers = [line_summary(x, cons_inputs.get(x.key, 0), cons_src.get(x.key, 0)) for x in db.scalars(
        select(ReturnLine).where(ReturnLine.version == version, ReturnLine.key.in_(consumer_keys))
        .order_by(ReturnLine.ordinal)).all()]

    refs = db.scalars(select(SourceRef).where(
        SourceRef.owner_type == "line", SourceRef.version == version, SourceRef.owner_key == key
    ).order_by(SourceRef.position)).all()
    sources = resolve_sources(db, list(refs), version)

    history = []
    for v in db.scalars(select(ReturnVersion).order_by(ReturnVersion.ordinal)).all():
        ln = idx.line(v.version, key)
        ch = db.scalar(select(VersionChange).where(VersionChange.version == v.version, VersionChange.key == key))
        history.append({"version": v.version, "computed_at": v.computed_at, "value": ln["value"] if ln else None,
                        "present": ln is not None, "change": ch.change if ch else None,
                        "old": ch.old if ch else None})

    prior_value = idx.prior_years["return_2024"]["lines"].get(key)
    prior_label = idx.prior_years["return_2024"]["line_labels"].get(key)

    adjustments = db.scalars(select(Adjustment).where(Adjustment.line_key == key).order_by(Adjustment.created_at)).all()
    overrides = effective_overrides(db, version)
    verifs = db.scalars(select(Verification).where(
        Verification.target_type == "line", Verification.target_id == key).order_by(Verification.at)).all()
    findings = db.scalars(select(Finding).where(any_(Finding.line_keys) == key)).all()
    notes = db.scalars(select(ReviewNote).where(
        ReviewNote.target_type == "line", ReviewNote.target_id == key).order_by(ReviewNote.created_at)).all()

    return {
        "key": r.key, "version": version, "form": r.form, "line": r.line, "label": r.label,
        "jurisdiction": r.jurisdiction, "value": r.value, "rule": r.rule,
        "rule_text": idx.rules.get(r.rule, "Rule not described in engine_reference"), "note": r.note,
        "inputs": inputs, "consumers": consumers, "sources": sources, "history": history,
        "prior_year": {"value": prior_value, "label": prior_label} if prior_value is not None else None,
        "effective": overrides.get(key),
        "adjustments": [adjustment_brief(a) for a in adjustments],
        "verifications": [{"id": v.id, "method": v.method, "note": v.note, "actor_id": v.actor_id, "at": v.at,
                           "evidence": v.evidence, "superseded": v.superseded} for v in verifs],
        "findings": [{"id": f.id, "title": f.title, "severity": f.severity, "status": f.status,
                      "category": f.category} for f in findings],
        "notes": [{"id": n.id, "kind": n.kind, "title": n.title, "status": n.status, "blocking": n.blocking}
                  for n in notes],
        "area": area_for_key(db, key),
    }


def adjustment_brief(a: Adjustment) -> dict:
    return {
        "id": a.id, "line_key": a.line_key, "original_value": float(a.original_value),
        "proposed_value": float(a.proposed_value), "delta": float(a.delta), "status": a.status,
        "fed_effect": float(a.fed_effect), "ca_effect": float(a.ca_effect), "reason": a.reason,
        "prepared_by": a.prepared_by, "decided_by": a.decided_by, "created_at": a.created_at,
        "decided_at": a.decided_at, "reverses_id": a.reverses_id, "reversed_by_id": a.reversed_by_id,
        "requires_partner": a.requires_partner, "finding_id": a.finding_id, "base_version": a.base_version,
    }


def compare(db: Session, a: str, b: str, changed_only: bool = True, q: str | None = None) -> dict:
    """Compare two engine versions or a version with a workpaper revision label (R1...)."""
    from app.services.revisions import revision_lines

    left = revision_lines(db, a)
    right = revision_lines(db, b)
    keys = list(dict.fromkeys(list(left["lines"].keys()) + list(right["lines"].keys())))
    rows = []
    for k in keys:
        lv, rv = left["lines"].get(k), right["lines"].get(k)
        lval = lv["value"] if lv else None
        rval = rv["value"] if rv else None
        if changed_only and lval == rval:
            continue
        label = (rv or lv)["label"]
        if q and q.lower() not in (k + label).lower():
            continue
        diff = None
        if num(lval) is not None and num(rval) is not None:
            diff = round(num(rval) - num(lval), 4)
        rows.append({"key": k, "label": label, "left": lval, "right": rval, "diff": diff,
                     "status": "added" if lv is None else "removed" if rv is None else
                     ("changed" if lval != rval else "same"),
                     "left_adjusted": bool(lv and lv.get("adjusted")), "right_adjusted": bool(rv and rv.get("adjusted"))})
    return {"left": {k: v for k, v in left.items() if k != "lines"},
            "right": {k: v for k, v in right.items() if k != "lines"}, "rows": rows}
