"""Resolve every reference format used in the packet to a concrete, navigable target.

Nothing is guessed: a reference that cannot be found is returned with resolved=False and a reason, and the UI
shows it as Unresolved.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.services.packet_index import LINE_KEY_RE, PacketIndex, json_pointer

EV_RE = re.compile(r"^ev-\d{4}$")
DOC_RE = re.compile(r"^D\d{2}$")
WP_DOC_RE = re.compile(r"^W-\d{4}$")
DOC_PAGE_RE = re.compile(r"^doc:(D\d{2}|W-\d{4})#page(\d+)$")
CLIENT_RE = re.compile(r"^(qa|msg|call)-\d+$")
VERSION_RE = re.compile(r"^v\d+$")

# Which packet document backs each prior-year / agency section (from the packet readme and extraction reasons).
PRIOR_SECTION_DOCS = {
    "return_2024": "D06",
    "prior_preparer_workpaper": "D07",
    "asset_records": "D07",
    "basis_records": "D07",
    "carryovers_into_2025": "D06",
}
AGENCY_SECTION_DOCS = {"irs_account_transcript_2025": "D69"}


@dataclass
class Resolved:
    raw_ref: str
    ref_type: str
    resolved: bool
    target_type: str | None = None
    target_id: str | None = None
    document_id: str | None = None
    page: int | None = None
    label: str | None = None
    value: Any = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify(ref: str) -> str:
    if EV_RE.match(ref):
        return "extracted_value"
    if DOC_RE.match(ref) or WP_DOC_RE.match(ref):
        return "document"
    if DOC_PAGE_RE.match(ref):
        return "document_page"
    if ref.startswith("py:"):
        return "prior_year"
    if ref.startswith("agency:"):
        return "agency"
    if ref.startswith("asset:"):
        return "asset"
    if ref.startswith("household:"):
        return "person"
    if ref.startswith("ref:param."):
        return "parameter"
    if ref.startswith("ref:fx."):
        return "fx_rate"
    if ref.startswith("timeline:"):
        return "timeline_event"
    if CLIENT_RE.match(ref):
        return "client_item"
    if VERSION_RE.match(ref):
        return "return_version"
    if LINE_KEY_RE.match(ref):
        return "return_line"
    return "unknown"


def _short(value: Any, limit: int = 160) -> Any:
    if isinstance(value, (dict, list)):
        text = str(value)
        return text if len(text) <= limit else text[:limit] + "…"
    return value


class Resolver:
    def __init__(self, idx: PacketIndex, extra_documents: dict[str, dict] | None = None):
        self.idx = idx
        self.extra_documents = extra_documents or {}

    def resolve(self, ref: str, version: str | None = None) -> Resolved:
        kind = classify(ref)
        handler = getattr(self, f"_r_{kind}", None)
        if handler is None:
            return Resolved(ref, kind, False, note="Unrecognized reference format")
        return handler(ref, version)

    # ----- handlers -----------------------------------------------------------------
    def _r_extracted_value(self, ref: str, version: str | None) -> Resolved:
        e = self.idx.ev.get(ref)
        if not e:
            return Resolved(ref, "extracted_value", False, note="Extracted value id not in packet")
        return Resolved(
            ref, "extracted_value", True, "extracted_value", ref, e["document_id"], e["page"], e["label"], e["value"]
        )

    def _r_document(self, ref: str, version: str | None) -> Resolved:
        d = self.idx.documents.get(ref) or self.extra_documents.get(ref)
        if not d:
            return Resolved(ref, "document", False, note="Document id not found")
        return Resolved(ref, "document", True, "document", ref, ref, None, d["title"])

    def _r_document_page(self, ref: str, version: str | None) -> Resolved:
        m = DOC_PAGE_RE.match(ref)
        assert m
        doc_id, page = m.group(1), int(m.group(2))
        d = self.idx.documents.get(doc_id) or self.extra_documents.get(doc_id)
        if not d or page < 1 or page > int(d.get("page_count", 0)):
            return Resolved(ref, "document_page", False, note="Document page not found")
        return Resolved(ref, "document_page", True, "document_page", f"{doc_id}#{page}", doc_id, page, d["title"])

    def _r_prior_year(self, ref: str, version: str | None) -> Resolved:
        pointer = ref[3:]
        found, value = json_pointer(self.idx.prior_years, pointer)
        if not found:
            return Resolved(ref, "prior_year", False, note=f"Pointer {pointer} not found in prior_years")
        parts = [p for p in pointer.split("/") if p]
        section = parts[0] if parts else ""
        doc_id = PRIOR_SECTION_DOCS.get(section)
        if section == "basis_records" and len(parts) > 1 and parts[1].startswith("home_"):
            doc_id = "D54"
        page = None
        label = " / ".join(parts)
        # A 2024 return line maps to the extracted value read from the filed return (D06).
        if section == "return_2024" and len(parts) >= 3 and parts[1] == "lines":
            line_key = parts[2]
            ev_id = self.idx.prior_years["return_2024"].get("line_sources", {}).get(line_key)
            label = "2024 " + self.idx.prior_years["return_2024"].get("line_labels", {}).get(line_key, line_key)
            if ev_id and ev_id in self.idx.ev:
                page = self.idx.ev[ev_id]["page"]
                return Resolved(ref, "prior_year", True, "prior_year", pointer, doc_id, page, label, value,
                                note=f"2024 return as filed; read as {ev_id}")
        return Resolved(ref, "prior_year", True, "prior_year", pointer, doc_id, page, label, _short(value))

    def _r_agency(self, ref: str, version: str | None) -> Resolved:
        pointer = ref[7:]
        found, value = json_pointer(self.idx.agency, pointer)
        if not found:
            return Resolved(ref, "agency", False, note=f"Pointer {pointer} not found in tax_agency_records")
        parts = [p for p in pointer.split("/") if p]
        section = parts[0] if parts else ""
        doc_id = AGENCY_SECTION_DOCS.get(section)
        if section == "notices" and len(parts) > 1 and isinstance(value, dict):
            doc_id = value.get("document")
        return Resolved(ref, "agency", True, "agency_record", pointer, doc_id, None, " / ".join(parts), _short(value))

    def _r_asset(self, ref: str, version: str | None) -> Resolved:
        asset_id = ref.split(":", 1)[1]
        if version and version in self.idx.versions:
            a = self.idx.assets(version).get(asset_id)
            if a:
                return Resolved(ref, "asset", True, "asset", f"{version}:{asset_id}", None, None, a["description"])
        a = self.idx.prior_assets().get(asset_id)
        if a:
            return Resolved(ref, "asset", True, "asset", f"prior:{asset_id}", "D07", None, a["description"],
                            note="Prior-year asset record")
        return Resolved(ref, "asset", False, note="Asset id not found in this version or prior-year records")

    def _r_person(self, ref: str, version: str | None) -> Resolved:
        pid = ref.split(":", 1)[1]
        p = self.idx.people.get(pid)
        if not p:
            return Resolved(ref, "person", False, note="Household member not found")
        return Resolved(ref, "person", True, "person", pid, None, None, f"{p['name']} ({p['role']})",
                        note="Household facts as entered by the client (organizer)")

    def _r_parameter(self, ref: str, version: str | None) -> Resolved:
        name = ref[len("ref:param."):]
        found, value = json_pointer(self.idx.params, "/" + name.replace(".", "/"))
        if not found:
            return Resolved(ref, "parameter", False, note="Engine parameter not found")
        return Resolved(ref, "parameter", True, "parameter", name, None, None, f"Engine parameter {name}",
                        _short(value))

    def _r_fx_rate(self, ref: str, version: str | None) -> Resolved:
        path = ref[len("ref:fx."):]
        found, value = json_pointer(self.idx.params.get("fx", {}), "/" + path.replace(".", "/"))
        if not found:
            return Resolved(ref, "fx_rate", False, note="Exchange rate not found")
        return Resolved(ref, "fx_rate", True, "parameter", f"fx.{path}", None, None, f"Exchange rate {path}", value)

    def _r_timeline_event(self, ref: str, version: str | None) -> Resolved:
        tid = ref.split(":", 1)[1]
        t = self.idx.timeline.get(tid)
        if not t:
            return Resolved(ref, "timeline_event", False, note="Timeline event not found")
        return Resolved(ref, "timeline_event", True, "timeline_event", tid, None, None,
                        f"{t['event']} ({t['at'][:10]})", t.get("detail"))

    def _r_client_item(self, ref: str, version: str | None) -> Resolved:
        c = self.idx.client_items.get(ref)
        if not c:
            return Resolved(ref, "client_item", False, note="Client communication not found")
        if c["kind"] == "questionnaire":
            label, value = c["question"], c["answer"]
        elif c["kind"] == "message":
            label, value = f"Message from {c['from']}", c["text"]
        else:
            label, value = "Call notes", " ".join(c["notes"])
        return Resolved(ref, "client_item", True, "client_item", ref, None, None, label, value)

    def _r_return_version(self, ref: str, version: str | None) -> Resolved:
        if ref not in self.idx.versions:
            return Resolved(ref, "return_version", False, note="Version not found")
        return Resolved(ref, "return_version", True, "return_version", ref, None, None,
                        f"Engine version {ref} ({self.idx.versions[ref]['computed_at'][:10]})")

    def _r_return_line(self, ref: str, version: str | None) -> Resolved:
        v = version or self.idx.current_version
        ln = self.idx.line(v, ref)
        if not ln:
            return Resolved(ref, "return_line", False, note=f"Line {ref} not present in {v}")
        return Resolved(ref, "return_line", True, "return_line", f"{v}:{ref}", None, None, ln["label"], ln["value"])
