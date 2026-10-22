"""Independent validation: source-linked findings, idempotent scans, reviewer decisions."""

from sqlalchemy import func, select

from app.models import AuditEvent, Finding, ReturnLine
from app.services.findings import run_validation
from tests.conftest import as_user


def test_rules_find_the_three_known_packet_issues(db):
    summary = run_validation(db, actor_id="st-01")
    assert summary["status"] == "ok"
    assert summary["detected"] >= 3
    rows = list(db.scalars(select(Finding)).all())
    by_rule: dict[str, list[Finding]] = {}
    for row in rows:
        by_rule.setdefault(row.rule_id, []).append(row)

    dup = next(f for f in by_rule["DUP-INCOME"] if set(f.line_keys) >= {"SchB.1.1", "SchB.1.2"})
    assert "ev-0492" in dup.evidence and "ev-0538" in dup.evidence
    assert "D28" in dup.evidence and "D29" in dup.evidence
    assert float(dup.affected_amount) == 1840

    fx = next(f for f in by_rule["FX-YEAR"] if "SchB.1.6" in f.line_keys)
    assert fx.details["used_rate"] == 10.56
    assert fx.details["current_year_rate"] == 9.86
    assert "ref:fx.SEK.2024_average" in fx.evidence

    ident = next(f for f in by_rule["IDENTITY-SSN"] if f.details["person_id"] == "theo")
    assert "household:theo" in ident.evidence
    assert ident.category == "needs_judgment"
    assert any(ref.startswith("ev-") for ref in ident.evidence)


def test_scan_does_not_change_return_lines_or_duplicate_findings(db):
    before = db.scalar(select(ReturnLine.value).where(ReturnLine.version == "v3", ReturnLine.key == "SchB.1.1"))
    first = run_validation(db, actor_id="st-01")
    second = run_validation(db, actor_id="st-01")
    assert second["created"] == 0
    assert second["detected"] == first["detected"]
    assert db.scalar(select(func.count()).select_from(Finding)) == first["findings"]
    fingerprints = db.scalars(select(Finding.fingerprint)).all()
    assert len(fingerprints) == len(set(fingerprints))
    after = db.scalar(select(ReturnLine.value).where(ReturnLine.version == "v3", ReturnLine.key == "SchB.1.1"))
    assert after == before == 1840


def test_reviewer_decision_is_audited_and_survives_rescan(client, db, fresh_workpaper):
    client.post("/api/validation/run", headers=as_user("st-01"))
    listed = client.get("/api/findings").json()["items"]
    dup = next(f for f in listed if f["rule_id"] == "DUP-INCOME" and "SchB.1.1" in f["line_keys"])
    denied = client.patch(f"/api/findings/{dup['id']}", headers=as_user("st-01"), json={
        "status": "false_positive", "note": "Preparer cannot dismiss.", "expected_version": dup["row_version"],
    })
    assert denied.status_code == 403

    ok = client.patch(f"/api/findings/{dup['id']}", headers=as_user("st-02"), json={
        "status": "resolved", "note": "Confirmed the bank sweep is already inside the composite 1099.",
        "expected_version": dup["row_version"],
    })
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["status"] == "resolved"
    assert body["notes"] and "composite" in body["notes"][-1]["body"]
    assert any(e["action"] == "finding.decide" for e in body["audit"])

    again = run_validation(db, actor_id="st-01")
    assert again["preserved"] >= 1
    kept = db.get(Finding, dup["id"])
    assert kept.status == "resolved"
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == dup["id"])).all()
    assert len(events) >= 1


def test_bidirectional_trace_and_field_location(client):
    line = client.get("/api/lines/SchB.1.1").json()
    src = next(s for s in line["sources"] if s["ref"] == "ev-0492")
    assert src["document_id"] == "D28" and src["page"] == 1
    assert src["position"]["x0"] < src["position"]["x1"]
    doc = client.get("/api/documents/D28").json()
    field = next(v for v in doc["values"] if v["id"] == "ev-0492")
    assert "SchB.1.1" in field["used_by"]["v3"]
    assert "SchB.1.1" in doc["direct_lines"]
    assert any(d["key"] == "SchB.2" for d in doc["downstream_lines"])
    assert doc["usage"]["status"] == "used"
    superseded = client.get("/api/documents/D30").json()
    assert superseded["usage"]["status"] == "superseded"
    assert superseded["marked_corrected"] is False
