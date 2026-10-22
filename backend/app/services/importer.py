"""Idempotent import of the packet into the baseline tables, plus seeding of workpaper configuration.

* The packet file is read-only; its SHA-256 identifies the baseline.
* Importing the same packet again is a no-op (counts are re-verified).
* Seeds (users, firm settings, areas, replay clock, extension record) are insert-if-missing, so human work in the
  workpaper layer is never overwritten by a re-import.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models import (
    AppUser,
    Asset,
    ClientItem,
    Diagnostic,
    Document,
    DocumentPage,
    EfileSubmission,
    ExtractedValue,
    FilingRecord,
    FirmSetting,
    LineInput,
    Notice,
    PacketImport,
    Person,
    ReferenceData,
    ReplayState,
    ReturnLine,
    ReturnVersion,
    SourceRef,
    TimelineEvent,
    VersionChange,
    WhatIfScenario,
    WorkpaperArea,
)
from app.services.areas_config import AREAS
from app.services.packet_index import PacketIndex
from app.services.resolver import Resolver

REFERENCE_SECTIONS = [
    "readme", "packet", "household", "prior_years", "tax_agency_records", "engine_reference", "firm",
    "planning_reference_2026", "post_filing_rates", "fx_rates",
]


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    if len(s) == 10:
        return datetime.fromisoformat(s + "T00:00:00+00:00")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s[:10]) if s else None


def _num(v: Any) -> Decimal | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    return None


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def baseline_counts(db: Session) -> dict[str, int]:
    def c(model) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0

    return {
        "documents": db.scalar(select(func.count()).select_from(Document).where(Document.origin == "packet")) or 0,
        "pages": c(DocumentPage),
        "extracted_values": c(ExtractedValue),
        "return_versions": c(ReturnVersion),
        "return_lines": c(ReturnLine),
        "line_inputs": c(LineInput),
        "source_refs": c(SourceRef),
        "unresolved_refs": db.scalar(select(func.count()).select_from(SourceRef).where(SourceRef.resolved.is_(False)))
        or 0,
        "timeline_events": c(TimelineEvent),
        "what_if_scenarios": c(WhatIfScenario),
        "client_items": c(ClientItem),
        "users": c(AppUser),
        "assets": c(Asset),
        "diagnostics": c(Diagnostic),
    }


def import_packet(db: Session, path: str) -> dict[str, Any]:
    path = os.path.abspath(path)
    sha = file_sha256(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    existing = db.scalar(select(PacketImport).where(PacketImport.sha256 == sha))
    if existing:
        seed_workpaper(db, raw)
        db.commit()
        return {"status": "already_imported", "sha256": sha, "counts": baseline_counts(db)}

    other = db.scalar(select(PacketImport))
    if other:
        raise RuntimeError(
            f"A different packet (sha256 {other.sha256[:12]}) is already imported. The baseline is immutable; "
            "reset the database to load a different packet."
        )

    idx = PacketIndex(raw)
    resolver = Resolver(idx)
    _insert_baseline(db, raw, idx, resolver)
    counts = baseline_counts(db)
    db.add(PacketImport(sha256=sha, file_name=os.path.basename(path), client_id=raw["packet"]["client_id"],
                        imported_at=datetime.now(UTC), counts=counts, raw=raw))
    seed_workpaper(db, raw)
    db.commit()
    return {"status": "imported", "sha256": sha, "counts": counts}


def _insert_baseline(db: Session, raw: dict, idx: PacketIndex, resolver: Resolver) -> None:
    for key in REFERENCE_SECTIONS:
        db.add(ReferenceData(key=key, data=raw[key]))
    db.add(ReferenceData(key="what_if_extension", data=raw["what_if"]["extension"]))

    for p in raw["household"]["people"]:
        db.add(Person(
            id=p["id"], role=p["role"], name=p["name"], ssn=p.get("ssn"), ip_pin=p.get("ip_pin"), dob=_d(p.get("dob")),
            occupation=p.get("occupation"), relationship=p.get("relationship"),
            months_lived_with_you=p.get("months_lived_with_you"), full_time_student=p.get("full_time_student"),
            phone=p.get("phone"), email=p.get("email"), note=p.get("note") or p.get("own_income"), raw=p,
        ))

    docs, pages, evs = [], [], []
    for d in raw["documents"]:
        ex = d["extraction"]
        docs.append(dict(
            id=d["id"], title=d["title"], document_type=d["document_type"], issuer=d.get("issuer"),
            belongs_to=d["belongs_to"], tax_year=d.get("tax_year"), received_at=_dt(d["received_at"]),
            uploaded_by=d["uploaded_by"], file_name=d.get("file_name"), page_count=d["page_count"],
            marked_corrected=bool(d.get("marked_corrected")), extraction_status=ex["status"],
            extraction_values=ex.get("values") or 0, extraction_reason=ex.get("reason"), origin="packet",
        ))
        for p in d["pages"]:
            pages.append(dict(document_id=d["id"], page=p["page"], printed_content=p["printed_content"]))
    for e in raw["extracted_values"]:
        pos = e["position"]
        evs.append(dict(
            id=e["id"], document_id=e["document_id"], page=e["page"], field=e["field"], label=e["label"],
            value=e["value"], value_num=_num(e["value"]), value_type=e["value_type"],
            text_as_read=e.get("text_as_read") or "", x0=pos["x0"], y0=pos["y0"], x1=pos["x1"], y1=pos["y1"],
            confidence=e["confidence"],
        ))
    db.execute(insert(Document), docs)
    db.execute(insert(DocumentPage), pages)
    db.execute(insert(ExtractedValue), evs)

    refs: list[dict] = []

    def add_refs(owner_type: str, owner_key: str, version: str | None, items: list[str]) -> None:
        for i, r in enumerate(items or []):
            res = resolver.resolve(r, version)
            refs.append(dict(
                owner_type=owner_type, owner_key=owner_key, version=version, position=i, raw_ref=r,
                ref_type=res.ref_type, target_type=res.target_type, target_id=res.target_id,
                document_id=res.document_id, page=res.page, resolved=res.resolved, resolution_note=res.note,
            ))

    for ordinal, v in enumerate(raw["return_versions"], start=1):
        ver = v["version"]
        db.add(ReturnVersion(
            version=ver, ordinal=ordinal, computed_at=_dt(v["computed_at"]), trigger=v["trigger"],
            summary=v["summary"], tax_effect_rates=v["tax_effect_rates"], carryovers_out=v["carryovers_out"],
            documents_used=v["documents_used"], documents_superseded=v["documents_superseded"],
        ))
        db.flush()
        line_rows = [dict(
            version=ver, key=ln["key"], ordinal=i, jurisdiction=ln["jurisdiction"], form=ln["form"], line=ln["line"],
            label=ln["label"], value=ln["value"], value_num=_num(ln["value"]), rule=ln["rule"], note=ln.get("note"),
        ) for i, ln in enumerate(v["lines"])]
        db.execute(insert(ReturnLine), line_rows)
        ids = dict(db.execute(select(ReturnLine.key, ReturnLine.id).where(ReturnLine.version == ver)).all())
        inputs = []
        for ln in v["lines"]:
            for pos, k in enumerate(ln.get("inputs") or []):
                inputs.append(dict(line_id=ids[ln["key"]], version=ver, line_key=ln["key"], input_key=k, position=pos))
            add_refs("line", ln["key"], ver, ln.get("sources") or [])
        if inputs:
            db.execute(insert(LineInput), inputs)
        for a in v["assets"]:
            db.add(Asset(version=ver, asset_id=a["asset_id"], description=a["description"], activity=a["activity"],
                         data=a))
            add_refs("asset", a["asset_id"], ver, a.get("sources") or [])
        for i, dg in enumerate(v["diagnostics"]):
            db.add(Diagnostic(version=ver, ordinal=i, code=dg["code"], severity=dg["severity"],
                              message=dg["message"], refs=dg.get("refs") or []))
            add_refs("diagnostic", f"{ver}:{i}:{dg['code']}", ver, dg.get("refs") or [])
        for i, ch in enumerate(v["changes_from_previous"]):
            db.add(VersionChange(version=ver, ordinal=i, key=ch["key"], change=ch["change"], old=ch.get("old"),
                                 new=ch.get("new")))

    for a in raw["prior_years"]["asset_records"]:
        db.add(Asset(version="prior", asset_id=a["asset_id"], description=a["description"], activity=a["activity"],
                     data=a))
    for line_key, ev_id in raw["prior_years"]["return_2024"].get("line_sources", {}).items():
        add_refs("prior_line", line_key, "2024", [ev_id])

    c = raw["client"]
    for q in c["questionnaire"]:
        db.add(ClientItem(id=q["id"], kind="questionnaire", at=_dt(q["answered_at"]), author=q["answered_by"],
                          recipient="firm", title=q["question"], body=q["answer"], raw=q))
    for m in c["messages"]:
        db.add(ClientItem(id=m["id"], kind="message", at=_dt(m["sent_at"]), author=m["from"], recipient=m["to"],
                          title=None, body=m["text"], raw=m))
    for n in c["call_notes"]:
        db.add(ClientItem(id=n["id"], kind="call_note", at=_dt(n["date"]), author=", ".join(n["participants"]),
                          recipient=None, title="Client call", body="\n".join(n["notes"]), raw=n))

    for i, t in enumerate(raw["timeline"]):
        db.add(TimelineEvent(id=t["id"], ordinal=i, at=_dt(t["at"]), event=t["event"], actor=t.get("actor"),
                             detail=t.get("detail"), refs=t.get("refs") or []))
        add_refs("timeline", t["id"], None, t.get("refs") or [])

    ag = raw["tax_agency_records"]
    for n in ag["notices"]:
        db.add(Notice(id=n["id"], agency=n["agency"], type=n["type"], tax_year=n["tax_year"], dated=_d(n["dated"]),
                      response_due=_d(n.get("response_due")), document_id=n.get("document"), status=n.get("status"),
                      raw=n))
    for i, s in enumerate(ag["efile"]):
        db.add(EfileSubmission(submission_id=s["submission_id"], ordinal=i, at=_dt(s["date"]),
                               jurisdiction=s["jurisdiction"], status=s["status"], errors=s.get("errors") or []))

    for i, w in enumerate(raw["what_if"]["alternatives"]):
        db.add(WhatIfScenario(id=w["id"], ordinal=i, description=w["description"], base_version=w["base_version"],
                              choices=w["choices"], federal=w["federal"], california=w["california"],
                              changed_lines=w["changed_lines"]))

    firm = raw["firm"]
    ptins = firm["firm_identity"].get("ptins", {})
    for s in firm["staff"]:
        db.add(AppUser(id=s["id"], name=s["name"], role=s["role"], kind="staff", credential=s.get("credential"),
                       sensitive_clearance=bool(s.get("sensitive_data_clearance")),
                       active_from=_d(s.get("active_from")), note=s.get("note"), ptin=ptins.get(s["id"])))
    people_by_name = {p["name"]: p["id"] for p in raw["household"]["people"]}
    for cu in firm["client_users"]:
        db.add(AppUser(id=cu["id"], name=cu["name"], role="client", kind="client", sensitive_clearance=False,
                       person_id=people_by_name.get(cu["name"])))

    db.flush()
    for i in range(0, len(refs), 2000):
        db.execute(insert(SourceRef), refs[i:i + 2000])


def default_settings(raw: dict) -> dict[str, Any]:
    std = raw["firm"]["starter_standards"]
    return {
        "verification_types": std["verification_types"],
        "variance_review": std["variance_review"],
        "review_levels": std["review_levels"],
        "rules": std["rules"],
        "required_steps": std["required_steps"],
        "budget_hours": raw["firm"]["budget_hours"],
        "partner_approval_threshold": 1000,
        "retention_years_after_filing": 7,
        "due_diligence_credits": [
            "child tax credit", "credit for other dependents", "American opportunity credit",
            "earned income credit", "head of household status",
        ],
        "low_confidence_threshold": 0.8,
    }


def seed_workpaper(db: Session, raw: dict) -> None:
    for key, value in default_settings(raw).items():
        if not db.get(FirmSetting, key):
            db.add(FirmSetting(key=key, value=value, version=1, updated_by="system"))

    assignment = raw["firm"]["assignment_at_start"]
    review_due = next((d["date"] for d in raw["firm"]["deadlines"] if "review complete" in d["what"]), None)
    for i, a in enumerate(AREAS):
        if not db.get(WorkpaperArea, a["id"]):
            db.add(WorkpaperArea(
                id=a["id"], ordinal=i, title=a["title"], description=a["description"], group=a["group"],
                line_prefixes=a["patterns"], budget_key=a["budget_key"], status="not_started",
                preparer_id=assignment["preparer"], reviewer_id=assignment["reviewer"], due_date=_d(review_due),
            ))

    if not db.get(ReplayState, 1):
        v3_at = max(_dt(v["computed_at"]) for v in raw["return_versions"])
        db.add(ReplayState(id=1, now=v3_at.replace(hour=12, minute=0), applied_event_ids=[]))

    has_ext = db.scalar(select(func.count()).select_from(FilingRecord).where(FilingRecord.kind == "extension"))
    if not has_ext:
        ext = raw["what_if"]["extension"]
        tl = next((t for t in raw["timeline"] if t["event"] == "extension_filed_with_payment"), None)
        at = _dt(tl["at"]) if tl else _dt(ext["computed_at"])
        for jur, key in (("federal", "paid_with_form_4868"), ("california", "paid_with_ftb_3519")):
            db.add(FilingRecord(
                jurisdiction=jur, kind="extension", status="accepted", revision_label=ext["based_on_version"],
                snapshot={"estimate": ext[jur]}, amount=Decimal(str(ext[jur][key])), submitted_at=at, accepted_at=at,
                source="packet", created_by=tl.get("actor") if tl else None,
                note=("Form 4868" if jur == "federal" else "FTB 3519")
                + f" — estimated from {ext['based_on_version']}; {ext[jur]['rule']}.",
            ))
