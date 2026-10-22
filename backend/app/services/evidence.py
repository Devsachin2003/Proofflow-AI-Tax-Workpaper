"""Evidence: document index, document viewer data, reverse tracing, unused-evidence reasons, attachments."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Invalid, NotFound
from app.core.masking import is_sensitive_field, mask_text, mask_value
from app.core.permissions import require
from app.models import (
    Comment,
    Document,
    DocumentPage,
    ExtractedValue,
    Finding,
    LineInput,
    ReturnLine,
    SourceRef,
    Verification,
)
from app.services import audit
from app.services.context import get_index, replay_now


def _version_lines_by_doc(db: Session, version: str) -> dict[str, set[str]]:
    rows = db.execute(select(SourceRef.document_id, SourceRef.owner_key).where(
        SourceRef.owner_type == "line", SourceRef.version == version, SourceRef.document_id.is_not(None))).all()
    out: dict[str, set[str]] = defaultdict(set)
    for doc_id, key in rows:
        out[doc_id].add(key)
    return out


def _cited_elsewhere(db: Session, version: str) -> dict[str, set[str]]:
    rows = db.execute(select(SourceRef.document_id, SourceRef.owner_type).where(
        SourceRef.owner_type.in_(["asset", "diagnostic"]), SourceRef.version == version,
        SourceRef.document_id.is_not(None))).all()
    out: dict[str, set[str]] = defaultdict(set)
    for doc_id, t in rows:
        out[doc_id].add(t)
    return out


def usage_status(db: Session, doc: Document, version: str, lines_by_doc=None, elsewhere=None) -> dict:
    """Classify how a document landed in `version` - or exactly why it did not."""
    idx = get_index(db)
    v = idx.versions.get(version)
    lines_by_doc = lines_by_doc if lines_by_doc is not None else _version_lines_by_doc(db, version)
    elsewhere = elsewhere if elsewhere is not None else _cited_elsewhere(db, version)
    lines = sorted(lines_by_doc.get(doc.id, set()))
    if doc.origin == "workpaper":
        return {"status": "workpaper_evidence", "lines": [], "reason": "Evidence attached in the workpaper."}
    if lines:
        return {"status": "used", "lines": lines, "reason": None}
    if doc.id in (v["documents_superseded"] if v else []):
        replacement = next((d for d, x in idx.documents.items() if x.get("marked_corrected")
                            and x["issuer"] == doc.issuer and d != doc.id), None)
        return {"status": "superseded", "lines": [],
                "reason": f"Superseded by corrected document {replacement or '(corrected version)'}"}
    if elsewhere.get(doc.id):
        kinds = " and ".join(sorted(elsewhere[doc.id]))
        return {"status": "used", "lines": [], "reason": f"Cited by engine {kinds} records (not by a return line)."}
    notes_citing = [ln["key"] for ln in (idx.lines.get(version) or {}).values()
                    if ln.get("note") and re.search(rf"\b{doc.id}\b", ln["note"])]
    if notes_citing:
        return {"status": "accounted", "lines": notes_citing,
                "reason": f"Accounted for in line note(s) {', '.join(notes_citing)}: "
                + idx.lines[version][notes_citing[0]]["note"]}
    if v and doc.received_at and doc.received_at.isoformat() > v["computed_at"].replace("Z", "+00:00"):
        return {"status": "received_after", "lines": [],
                "reason": f"Received {doc.received_at.date()} after {version} was computed ({v['computed_at'][:10]})."}
    if doc.extraction_status == "not_extracted":
        return {"status": "not_extracted", "lines": [], "reason": f"Not extracted by the pipeline: {doc.extraction_reason}"}
    if v and doc.id in v["documents_used"]:
        return {"status": "context", "lines": [],
                "reason": "Listed as used by the engine, but no return line cites its values "
                          "(supporting or administrative document)."}
    return {"status": "unexplained", "lines": [],
            "reason": "Not used by the engine and no reason recorded - requires review."}


def list_documents(db: Session, version: str, q: str | None = None, document_type: str | None = None,
                   belongs_to: str | None = None, usage: str | None = None, extraction: str | None = None,
                   corrected: bool | None = None, with_findings: bool | None = None,
                   review: str | None = None, include_future: bool = False) -> dict:
    now = replay_now(db)
    docs = db.scalars(select(Document).order_by(Document.id)).all()
    lines_by_doc = _version_lines_by_doc(db, version)
    elsewhere = _cited_elsewhere(db, version)
    ev_counts = dict(db.execute(select(ExtractedValue.document_id, func.count()).group_by(
        ExtractedValue.document_id)).all())
    verified = dict(db.execute(
        select(ExtractedValue.document_id, func.count(func.distinct(Verification.target_id)))
        .join(Verification, (Verification.target_type == "ev") & (Verification.target_id == ExtractedValue.id)
              & Verification.superseded.is_(False))
        .group_by(ExtractedValue.document_id)).all())
    doc_verified = set(db.scalars(select(Verification.target_id).where(
        Verification.target_type == "document", Verification.superseded.is_(False))).all())
    finding_docs: dict[str, int] = defaultdict(int)
    idx = get_index(db)
    for f in db.scalars(select(Finding).where(Finding.status.in_(["open", "in_review"]))).all():
        for d in {_doc_of_ref(idx, r) for r in f.evidence} - {None}:
            finding_docs[d] += 1
    low_conf = dict(db.execute(select(ExtractedValue.document_id, func.count()).where(
        ExtractedValue.confidence < 0.8).group_by(ExtractedValue.document_id)).all())

    items = []
    for d in docs:
        future = bool(now and d.received_at and d.received_at > now)
        if future and not include_future:
            continue
        u = usage_status(db, d, version, lines_by_doc, elsewhere)
        n = ev_counts.get(d.id, 0)
        nver = verified.get(d.id, 0)
        rstatus = "verified" if (d.id in doc_verified or (n and nver >= n)) else "partial" if nver else "unreviewed"
        item = {
            "id": d.id, "title": d.title, "document_type": d.document_type, "issuer": d.issuer,
            "belongs_to": d.belongs_to, "tax_year": d.tax_year, "received_at": d.received_at,
            "uploaded_by": d.uploaded_by, "page_count": d.page_count, "marked_corrected": d.marked_corrected,
            "extraction_status": d.extraction_status, "values": n, "verified_values": nver,
            "review_status": rstatus, "usage": u["status"], "usage_reason": u["reason"], "lines": len(u["lines"]),
            "open_findings": finding_docs.get(d.id, 0), "low_confidence_values": low_conf.get(d.id, 0),
            "origin": d.origin, "not_yet_received": future, "evidence_kind": d.evidence_kind,
        }
        items.append(item)

    def keep(i: dict) -> bool:
        if q and q.lower() not in f"{i['id']} {i['title']} {i['issuer']} {i['document_type']}".lower():
            return False
        if document_type and i["document_type"] != document_type:
            return False
        if belongs_to and i["belongs_to"] != belongs_to:
            return False
        if usage and i["usage"] != usage:
            return False
        if extraction and i["extraction_status"] != extraction:
            return False
        if corrected is not None and i["marked_corrected"] != corrected:
            return False
        if with_findings and not i["open_findings"]:
            return False
        return not (review and i["review_status"] != review)

    filtered = [i for i in items if keep(i)]
    facets = {
        "document_type": sorted({i["document_type"] for i in items}),
        "belongs_to": sorted({i["belongs_to"] for i in items}),
        "usage": sorted({i["usage"] for i in items}),
        "extraction_status": sorted({i["extraction_status"] for i in items}),
    }
    return {"total": len(filtered), "items": filtered, "facets": facets,
            "counts": {"all": len(items), "used": sum(i["usage"] == "used" for i in items),
                       "not_used": sum(i["usage"] not in ("used", "accounted", "workpaper_evidence") for i in items)}}


def _doc_of_ref(idx, ref: str) -> str | None:
    if ref in idx.documents or re.match(r"^W-\d{4}$", ref):
        return ref
    if ref in idx.ev:
        return idx.ev[ref]["document_id"]
    m = re.match(r"^doc:(D\d{2}|W-\d{4})#page\d+$", ref)
    return m.group(1) if m else None


def document_detail(db: Session, doc_id: str, version: str) -> dict:
    d = db.get(Document, doc_id)
    if not d:
        raise NotFound(f"Document {doc_id} not found")
    idx = get_index(db)
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == doc_id).order_by(DocumentPage.page)).all()
    values = db.scalars(select(ExtractedValue).where(ExtractedValue.document_id == doc_id).order_by(
        ExtractedValue.page, ExtractedValue.id)).all()
    ev_ids = [v.id for v in values]

    citing = db.execute(select(SourceRef.target_id, SourceRef.owner_type, SourceRef.owner_key, SourceRef.version)
                        .where(SourceRef.target_id.in_(ev_ids))).all() if ev_ids else []
    by_ev: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for ev_id, owner_type, owner_key, ver in citing:
        if owner_type == "line":
            by_ev[ev_id][ver].append(owner_key)
        elif owner_type == "prior_line":
            by_ev[ev_id]["2024"].append(owner_key)
        else:
            by_ev[ev_id][f"{ver}:{owner_type}"].append(owner_key)

    verifs = db.scalars(select(Verification).where(
        Verification.target_type == "ev", Verification.target_id.in_(ev_ids), Verification.superseded.is_(False)
    )).all() if ev_ids else []
    vmap = {v.target_id: v for v in verifs}
    findings = db.scalars(select(Finding)).all()
    ev_findings: dict[str, list[dict]] = defaultdict(list)
    doc_findings = []
    for f in findings:
        refs = set(f.evidence or [])
        brief = {"id": f.id, "title": f.title, "severity": f.severity, "status": f.status, "category": f.category}
        if doc_id in refs or any(_doc_of_ref(idx, r) == doc_id for r in refs):
            doc_findings.append(brief)
        for r in refs & set(ev_ids):
            ev_findings[r].append(brief)

    direct_lines = sorted({k for ev in by_ev.values() for k in ev.get(version, [])})
    downstream = downstream_lines(db, version, direct_lines, limit=60)
    usage = usage_status(db, d, version)
    comments = db.scalars(select(Comment).where(Comment.target_type == "document", Comment.target_id == doc_id)
                          .order_by(Comment.created_at)).all()

    related = []
    for other_id, other in idx.documents.items():
        if other_id != doc_id and other.get("issuer") == d.issuer and d.issuer:
            related.append({"id": other_id, "title": other["title"], "relation": "same issuer"})

    return {
        "id": d.id, "title": d.title, "document_type": d.document_type, "issuer": d.issuer,
        "belongs_to": d.belongs_to, "tax_year": d.tax_year, "received_at": d.received_at,
        "uploaded_by": d.uploaded_by, "file_name": d.file_name, "page_count": d.page_count,
        "marked_corrected": d.marked_corrected, "extraction": {"status": d.extraction_status,
                                                               "values": d.extraction_values,
                                                               "reason": d.extraction_reason},
        "origin": d.origin, "evidence_kind": d.evidence_kind, "attached_by": d.attached_by,
        "attached_to": d.attached_to,
        "simulated": True,
        "pages": [{"page": p.page, "printed_content": mask_text(p.printed_content)} for p in pages],
        "values": [
            {
                "id": v.id, "page": v.page, "field": v.field, "label": v.label,
                "value": mask_value(v.value_type, v.value) if is_sensitive_field(v.field, v.value_type) else v.value,
                "sensitive": is_sensitive_field(v.field, v.value_type),
                "value_type": v.value_type, "text_as_read": mask_text(v.text_as_read)
                if is_sensitive_field(v.field, v.value_type) else v.text_as_read,
                "position": {"x0": v.x0, "y0": v.y0, "x1": v.x1, "y1": v.y1}, "confidence": v.confidence,
                "used_by": {k: sorted(set(x)) for k, x in by_ev.get(v.id, {}).items()},
                "verification": {"method": vmap[v.id].method, "actor_id": vmap[v.id].actor_id,
                                 "at": vmap[v.id].at, "note": vmap[v.id].note} if v.id in vmap else None,
                "findings": ev_findings.get(v.id, []),
            }
            for v in values
        ],
        "usage": usage,
        "direct_lines": direct_lines,
        "downstream_lines": downstream,
        "findings": doc_findings,
        "related": related[:10],
        "comments": [{"id": c.id, "author_id": c.author_id, "body": c.body, "kind": c.kind,
                      "created_at": c.created_at} for c in comments],
    }


def downstream_lines(db: Session, version: str, keys: list[str], limit: int = 60) -> list[dict]:
    """Transitive consumers of the given lines (breadth-first), capped for readability."""
    seen = set(keys)
    frontier = list(keys)
    order: list[str] = []
    while frontier and len(order) < limit:
        consumers = db.scalars(select(LineInput.line_key).where(
            LineInput.version == version, LineInput.input_key.in_(frontier))).all()
        frontier = [c for c in dict.fromkeys(consumers) if c not in seen]
        seen.update(frontier)
        order.extend(frontier)
    order = order[:limit]
    rows = {r.key: r for r in db.scalars(select(ReturnLine).where(
        ReturnLine.version == version, ReturnLine.key.in_(order))).all()}
    return [{"key": k, "label": rows[k].label, "value": rows[k].value} for k in order if k in rows]


def value_detail(db: Session, ev_id: str) -> dict:
    v = db.get(ExtractedValue, ev_id)
    if not v:
        raise NotFound(f"Extracted value {ev_id} not found")
    detail = document_detail(db, v.document_id, get_index(db).current_version)
    item = next(x for x in detail["values"] if x["id"] == ev_id)
    page = next(p for p in detail["pages"] if p["page"] == v.page)
    return {"value": item, "document": {k: detail[k] for k in ("id", "title", "document_type", "issuer")},
            "page": page}


def next_workpaper_doc_id(db: Session) -> str:
    ids = db.scalars(select(Document.id).where(Document.origin == "workpaper")).all()
    n = max((int(i.split("-")[1]) for i in ids), default=0) + 1
    return f"W-{n:04d}"


def attach_evidence(db: Session, user, *, kind: str, title: str, content: str, file_name: str | None,
                    attached_to: str | None) -> dict:
    require(user, "evidence.attach")
    if kind not in ("file", "message", "note"):
        raise Invalid("kind must be file, message or note")
    if not content.strip():
        raise Invalid("Evidence content is required")
    doc_id = next_workpaper_doc_id(db)
    doc = Document(
        id=doc_id, title=title, document_type=f"workpaper_{kind}", issuer=user.name, belongs_to="joint",
        tax_year=2025, received_at=datetime.now(UTC), uploaded_by="client" if user.kind == "client" else "firm",
        file_name=file_name, page_count=1, marked_corrected=False, extraction_status="not_extracted",
        extraction_values=0, extraction_reason="Attached in the workpaper; content stored as entered.",
        origin="workpaper", evidence_kind=kind, attached_by=user.id, attached_to=attached_to,
    )
    db.add(doc)
    db.flush()
    db.add(DocumentPage(document_id=doc_id, page=1, printed_content=content))
    audit.record(db, actor=user, action="evidence.attach", entity_type="document", entity_id=doc_id,
                 summary=f"Attached {kind} '{title}'" + (f" to {attached_to}" if attached_to else ""),
                 after={"title": title, "kind": kind, "attached_to": attached_to})
    db.commit()
    return {"id": doc_id}
