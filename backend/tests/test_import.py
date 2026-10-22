import json

import pytest
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.models import (
    AuditEvent,
    Document,
    ExtractedValue,
    PacketImport,
    ReturnLine,
    ReturnVersion,
    SourceRef,
    WorkpaperArea,
)
from app.services.importer import file_sha256, import_packet


@pytest.fixture(scope="module")
def packet():
    with open(get_settings().packet_path, encoding="utf-8") as f:
        return json.load(f)


def test_import_counts_match_packet(database, packet):
    counts = database["counts"]
    assert counts["documents"] == len(packet["documents"]) == 74
    assert counts["extracted_values"] == len(packet["extracted_values"]) == 3012
    assert counts["return_versions"] == 3
    assert counts["return_lines"] == sum(len(v["lines"]) for v in packet["return_versions"])
    assert counts["timeline_events"] == len(packet["timeline"]) == 29
    assert counts["what_if_scenarios"] == len(packet["what_if"]["alternatives"]) == 5
    assert counts["pages"] == sum(len(d["pages"]) for d in packet["documents"])


def test_every_source_reference_resolves(db):
    unresolved = db.scalars(select(SourceRef.raw_ref).where(SourceRef.resolved.is_(False))).all()
    assert unresolved == []


def test_import_is_idempotent(db):
    before = db.scalar(select(func.count()).select_from(ReturnLine))
    result = import_packet(db, get_settings().packet_path)
    assert result["status"] == "already_imported"
    assert db.scalar(select(func.count()).select_from(ReturnLine)) == before
    assert db.scalar(select(func.count()).select_from(PacketImport)) == 1


def test_baseline_stored_verbatim(db, packet):
    pkt = db.scalar(select(PacketImport))
    assert pkt.sha256 == file_sha256(get_settings().packet_path)
    assert pkt.raw == packet


def test_extracted_values_preserve_misreads(db, packet):
    by_id = {e["id"]: e for e in packet["extracted_values"]}
    for ev in db.scalars(select(ExtractedValue).limit(500)).all():
        src = by_id[ev.id]
        assert ev.value == src["value"]
        assert ev.text_as_read == (src.get("text_as_read") or "")
        assert ev.confidence == src["confidence"]


def test_engine_lines_kept_as_computed(db, packet):
    v3 = next(v for v in packet["return_versions"] if v["version"] == "v3")
    line = db.scalar(select(ReturnLine).where(ReturnLine.version == "v3", ReturnLine.key == "SchB.1.6"))
    src = next(ln for ln in v3["lines"] if ln["key"] == "SchB.1.6")
    assert line.value == src["value"]
    assert db.get(ReturnVersion, "v3").summary == v3["summary"]


def test_seeds_are_insert_if_missing(db):
    area = db.get(WorkpaperArea, "interest-dividends")
    assert area is not None and area.preparer_id == "st-01" and area.reviewer_id == "st-02"
    assert db.scalar(select(func.count()).select_from(WorkpaperArea)) == 20


def test_packet_documents_have_simulated_pages(db):
    doc = db.get(Document, "D23")
    assert doc.page_count == 4 and doc.origin == "packet"


def test_audit_log_is_append_only(db):
    from app.services import audit

    audit.record(db, actor="st-01", action="test.event", entity_type="test", entity_id="1", summary="x")
    db.commit()
    eid = db.scalar(select(AuditEvent.id).order_by(AuditEvent.id.desc()))
    with pytest.raises(Exception, match="append-only"):
        db.execute(text("UPDATE audit_event SET summary = 'tampered' WHERE id = :i"), {"i": eid})
    db.rollback()
    with pytest.raises(Exception, match="append-only"):
        db.execute(text("DELETE FROM audit_event WHERE id = :i"), {"i": eid})
    db.rollback()
