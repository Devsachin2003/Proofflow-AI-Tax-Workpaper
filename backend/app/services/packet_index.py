"""In-memory, read-only index over the immutable packet.

The packet is small (~2 MB), immutable, and stored verbatim in `packet_import.raw`. Rules and resolvers work
against this index so that independent checks read the same baseline the importer stored, never the API's
mutable workpaper layer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

LINE_KEY_RE = re.compile(r"^[A-Za-z0-9-]+\.[A-Za-z0-9.\-]+$")


@dataclass
class PacketIndex:
    raw: dict[str, Any]
    documents: dict[str, dict] = field(init=False)
    pages: dict[tuple[str, int], str] = field(init=False)
    ev: dict[str, dict] = field(init=False)
    ev_by_doc: dict[str, list[dict]] = field(init=False)
    versions: dict[str, dict] = field(init=False)
    lines: dict[str, dict[str, dict]] = field(init=False)
    client_items: dict[str, dict] = field(init=False)
    timeline: dict[str, dict] = field(init=False)
    people: dict[str, dict] = field(init=False)

    def __post_init__(self) -> None:
        r = self.raw
        self.documents = {d["id"]: d for d in r["documents"]}
        self.pages = {(d["id"], p["page"]): p["printed_content"] for d in r["documents"] for p in d["pages"]}
        self.ev = {e["id"]: e for e in r["extracted_values"]}
        self.ev_by_doc = {}
        for e in r["extracted_values"]:
            self.ev_by_doc.setdefault(e["document_id"], []).append(e)
        self.versions = {v["version"]: v for v in r["return_versions"]}
        self.lines = {v["version"]: {ln["key"]: ln for ln in v["lines"]} for v in r["return_versions"]}
        c = r["client"]
        self.client_items = {}
        for q in c["questionnaire"]:
            self.client_items[q["id"]] = {"kind": "questionnaire", **q}
        for m in c["messages"]:
            self.client_items[m["id"]] = {"kind": "message", **m}
        for n in c["call_notes"]:
            self.client_items[n["id"]] = {"kind": "call_note", **n}
        self.timeline = {t["id"]: t for t in r["timeline"]}
        self.people = {p["id"]: p for p in r["household"]["people"]}

    @classmethod
    def from_file(cls, path: str) -> PacketIndex:
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    # ----- convenience accessors -------------------------------------------------
    @property
    def current_version(self) -> str:
        return max(self.versions, key=lambda v: self.versions[v]["computed_at"])

    @cached_property
    def params(self) -> dict[str, Any]:
        return self.raw["engine_reference"]["parameters"]

    @cached_property
    def rules(self) -> dict[str, str]:
        return self.raw["engine_reference"]["rules"]

    @property
    def prior_years(self) -> dict[str, Any]:
        return self.raw["prior_years"]

    @property
    def agency(self) -> dict[str, Any]:
        return self.raw["tax_agency_records"]

    def line(self, version: str, key: str) -> dict | None:
        return self.lines.get(version, {}).get(key)

    def line_value(self, version: str, key: str) -> Any:
        ln = self.line(version, key)
        return None if ln is None else ln["value"]

    def assets(self, version: str) -> dict[str, dict]:
        return {a["asset_id"]: a for a in self.versions[version]["assets"]}

    def prior_assets(self) -> dict[str, dict]:
        return {a["asset_id"]: a for a in self.prior_years["asset_records"]}

    def page_text(self, doc_id: str, page: int) -> str:
        return self.pages.get((doc_id, page), "")

    def doc_text(self, doc_id: str) -> str:
        doc = self.documents.get(doc_id)
        if not doc:
            return ""
        return "\n".join(p["printed_content"] for p in doc["pages"])

    def evs(self, doc_id: str, field_name: str | None = None) -> list[dict]:
        items = self.ev_by_doc.get(doc_id, [])
        return [e for e in items if field_name is None or e["field"] == field_name]


def json_pointer(doc: Any, pointer: str) -> tuple[bool, Any]:
    """Resolve an RFC 6901 JSON pointer. Returns (found, value)."""
    if pointer in ("", "/"):
        return True, doc
    if not pointer.startswith("/"):
        return False, None
    cur = doc
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if token not in cur:
                return False, None
            cur = cur[token]
        elif isinstance(cur, list):
            if not token.isdigit() or int(token) >= len(cur):
                return False, None
            cur = cur[int(token)]
        else:
            return False, None
    return True, cur
