"""Command-center payload: return totals, prior-year comparison, queues, and filing snapshot."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.masking import mask_ssn
from app.models import Diagnostic, Finding, PacketImport, ReplayState, ReturnVersion, WorkpaperArea
from app.services.context import get_index
from app.services.evidence import list_documents
from app.services.revisions import active_base_version, working_state


def overview(db: Session) -> dict:
    idx = get_index(db)
    version = active_base_version(db)
    v = idx.versions[version]
    py_lines = idx.prior_years["return_2024"]["lines"]
    py_labels = idx.prior_years["return_2024"].get("line_labels") or {}
    working = working_state(db)
    docs = list_documents(db, version, include_future=False)
    findings = list(db.scalars(select(Finding).where(Finding.status.in_(["open", "in_review"]))))
    diagnostics = list(db.scalars(
        select(Diagnostic).where(Diagnostic.version == version).order_by(Diagnostic.ordinal)
    ))
    areas = list(db.scalars(select(WorkpaperArea).order_by(WorkpaperArea.ordinal)))
    state = db.get(ReplayState, 1)
    pkt = db.scalar(select(PacketImport))

    federal = v["summary"]["federal"]
    california = v["summary"]["california"]
    py_agi = idx.raw["household"].get("prior_year_agi_for_esignature")
    py_tax = idx.params.get("prior_year_tax")
    py_ca_tax = idx.params.get("ca_prior_year_tax")

    queue = _priority_queue(diagnostics, findings, docs["items"])
    hh = idx.raw["household"]

    return {
        "household": {
            "name": idx.raw["packet"]["name"],
            "client_id": idx.raw["packet"]["client_id"],
            "tax_year": hh["tax_year"],
            "filing_status": hh["filing_status"],
            "people": [
                {
                    "id": p["id"], "role": p["role"], "name": p["name"],
                    "ssn_masked": mask_ssn(p.get("ssn")), "occupation": p.get("occupation"),
                }
                for p in hh["people"]
            ],
            "residency": hh["residency"],
            "addresses": hh["addresses"],
        },
        "active_version": version,
        "computed_at": v["computed_at"],
        "trigger": v["trigger"],
        "working_revision": {
            "label": working["label"],
            "fingerprint": working["fingerprint"],
            "adjustment_count": working["summary"].get("adjustment_count", 0),
            "estimated": working["summary"].get("estimated", False),
        },
        "federal": {
            **federal,
            "prior_year": {"agi": py_agi, "total_tax": py_tax, "line_agi": py_lines.get("F1040.11")},
            "yoy": {
                "agi": _delta(federal.get("agi"), py_agi),
                "total_tax": _delta(federal.get("total_tax"), py_tax),
            },
        },
        "california": {
            **california,
            "prior_year": {"total_tax": py_ca_tax},
            "yoy": {"total_tax": _delta(california.get("total_tax"), py_ca_tax)},
        },
        "drilldowns": {
            "federal_agi": "F1040.11",
            "federal_taxable_income": "F1040.15",
            "federal_total_tax": "F1040.24",
            "federal_balance_due": "F1040.37",
            "california_agi": "F540NR.17",
            "california_total_tax": "F540NR.64",
        },
        "documents": docs["counts"] | {"visible": docs["total"], "packet": 74},
        "findings": {
            "open": len(findings),
            "blocking": sum(1 for f in findings if f.blocks_filing),
            "engine_diagnostics": sum(1 for d in diagnostics if d.severity == "warning"),
            "informational_diagnostics": sum(1 for d in diagnostics if d.severity == "info"),
        },
        "areas": {
            "total": len(areas),
            "not_started": sum(1 for a in areas if a.status == "not_started"),
            "in_review": sum(1 for a in areas if a.status == "in_review"),
            "signed": sum(1 for a in areas if a.status in ("signed", "complete")),
        },
        "priority_queue": queue,
        "filing": {
            "lifecycle": "preparation",
            "replay_now": state.now if state else None,
            "note": (
                "v3 is the latest engine output. Timeline events after 2026-06-23 are scripted for replay "
                "and are not treated as completed until the clock advances."
            ),
            "required_signatures": ["preparer", "reviewer", "partner", "client_approval", "efile_authorization"],
            "open_blocking_notes": 0,
        },
        "prior_year_highlights": [
            {"key": k, "label": py_labels.get(k, k), "value": py_lines[k]}
            for k in ("F1040.11", "F1040.15", "F1040.24", "F1040.37") if k in py_lines
        ],
        "imported_at": pkt.imported_at if pkt else None,
    }


def household(db: Session) -> dict:
    idx = get_index(db)
    hh = idx.raw["household"]
    return {
        "filing_status": hh["filing_status"],
        "tax_year": hh["tax_year"],
        "entered_by": hh.get("entered_by"),
        "people": [
            {
                "id": p["id"], "role": p["role"], "name": p["name"],
                "ssn_masked": mask_ssn(p.get("ssn")),
                "ip_pin_present": bool(p.get("ip_pin")),
                "dob": p.get("dob"), "occupation": p.get("occupation"),
                "relationship": p.get("relationship"),
                "months_lived_with_you": p.get("months_lived_with_you"),
                "full_time_student": p.get("full_time_student"),
                "note": p.get("note") or p.get("own_income"),
            }
            for p in hh["people"]
        ],
        "addresses": hh["addresses"],
        "residency": hh["residency"],
        "related_returns": hh.get("related_returns") or [],
        "prior_year_agi_for_esignature": hh.get("prior_year_agi_for_esignature"),
        "bank": {"bank": hh["bank_account_for_refund_or_payment"].get("bank"),
                 "type": hh["bank_account_for_refund_or_payment"].get("type"),
                 "masked": True},
    }


def timeline(db: Session, include_future: bool = False) -> dict:
    idx = get_index(db)
    state = db.get(ReplayState, 1)
    now = state.now if state else None
    events = []
    for t in idx.raw["timeline"]:
        stamp = t["at"].replace("Z", "+00:00")
        is_future = bool(now and stamp > now.isoformat())
        if is_future and not include_future:
            events.append({**t, "status": "scripted", "visible": False})
            continue
        events.append({**t, "status": "scripted" if is_future else "occurred", "visible": True})
    visible = [e for e in events if e["visible"]]
    return {
        "now": now,
        "total": len(events),
        "visible": len(visible),
        "items": events if include_future else visible,
        "scripted_remaining": sum(1 for e in events if e["status"] == "scripted"),
    }


def areas(db: Session) -> list[dict]:
    version = active_base_version(db)
    rows = db.scalars(select(WorkpaperArea).order_by(WorkpaperArea.ordinal)).all()
    finding_counts = dict(
        db.execute(
            select(Finding.area_id, func.count()).where(Finding.status.in_(["open", "in_review"]))
            .group_by(Finding.area_id)
        ).all()
    )
    return [
        {
            "id": a.id, "ordinal": a.ordinal, "title": a.title, "description": a.description,
            "group": a.group, "status": a.status, "preparer_id": a.preparer_id,
            "reviewer_id": a.reviewer_id, "due_date": a.due_date, "budget_key": a.budget_key,
            "open_findings": finding_counts.get(a.id, 0), "version": version,
        }
        for a in rows
    ]


def scenarios(db: Session) -> list[dict]:
    idx = get_index(db)
    out = []
    for w in idx.raw["what_if"]["alternatives"]:
        out.append({
            "id": w["id"], "description": w["description"], "base_version": w["base_version"],
            "choices": w["choices"],
            "federal": {k: w["federal"][k] for k in ("base", "alternative", "total_tax_change", "penalty_change")
                        if k in w["federal"]},
            "california": {k: w["california"][k] for k in ("base", "alternative", "total_tax_change", "penalty_change")
                           if k in w["california"]},
            "changed_line_count": len(w.get("changed_lines") or []),
        })
    return out


def diagnostics(db: Session, version: str | None = None) -> list[dict]:
    version = version or active_base_version(db)
    rows = db.scalars(select(Diagnostic).where(Diagnostic.version == version).order_by(Diagnostic.ordinal)).all()
    return [{"code": d.code, "severity": d.severity, "message": d.message, "refs": d.refs, "version": d.version}
            for d in rows]


def _delta(current, prior) -> dict | None:
    if current is None or prior is None:
        return None
    try:
        diff = float(current) - float(prior)
    except (TypeError, ValueError):
        return None
    pct = None if not prior else round(diff / float(prior) * 100, 1)
    return {"amount": round(diff, 2), "percent": pct}


def _priority_queue(diagnostics: list[Diagnostic], findings: list[Finding], docs: list[dict]) -> list[dict]:
    items: list[dict] = []
    for f in findings:
        items.append({
            "id": f.id, "kind": "finding", "severity": f.severity, "title": f.title,
            "amount": float(f.affected_amount) if f.affected_amount is not None else None,
            "blocks_filing": f.blocks_filing, "href": f"/findings/{f.id}",
        })
    for d in diagnostics:
        items.append({
            "id": d.code, "kind": "engine_diagnostic", "severity": d.severity,
            "title": d.message, "amount": None, "blocks_filing": d.severity == "warning",
            "href": "/findings",
        })
    unused = [doc for doc in docs if doc["usage"] in ("unexplained", "superseded") or doc.get("low_confidence_values")]
    for doc in unused[:8]:
        items.append({
            "id": doc["id"], "kind": "document", "severity": "warning" if doc["usage"] == "unexplained" else "info",
            "title": f"{doc['id']}: {doc['usage_reason'] or doc['title']}",
            "amount": None, "blocks_filing": False, "href": f"/evidence/{doc['id']}",
        })
    rank = {"error": 0, "warning": 1, "info": 2}
    items.sort(key=lambda x: (0 if x["blocks_filing"] else 1, rank.get(x["severity"], 9)))
    return items[:20]
