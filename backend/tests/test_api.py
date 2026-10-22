from tests.conftest import as_user


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "packet_imported": True}


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["counts"]["documents"] == 74
    assert body["counts"]["extracted_values"] == 3012
    assert body["counts"]["return_versions"] == 3
    assert body["counts"]["timeline_events"] == 29
    assert body["counts"]["what_if_scenarios"] == 5
    assert body["active_version"] == "v3"


def test_overview_uses_v3_totals(client):
    body = client.get("/api/overview").json()
    assert body["active_version"] == "v3"
    assert body["federal"]["agi"] == 445590
    assert body["federal"]["total_tax"] == 81962
    assert body["california"]["total_tax"] == 18874
    assert body["household"]["client_id"] == "CL-20417"
    assert body["documents"]["packet"] == 74
    assert body["priority_queue"]


def test_me_reports_permissions(client):
    body = client.get("/api/me", headers=as_user("st-04")).json()
    assert body["role"] == "preparer" and body["sensitive_clearance"] is False
    assert "adjustment.propose" in body["permissions"]
    assert "adjustment.decide" not in body["permissions"]


def test_line_detail_traces_to_evidence(client):
    body = client.get("/api/lines/SchB.1.6").json()
    assert body["value"] == 1747
    refs = {s["ref"]: s for s in body["sources"]}
    assert refs["ev-0960"]["document_id"] == "D36"
    assert refs["ev-0960"]["position"]["x0"] > 0
    assert refs["ref:fx.SEK.2024_average"]["value"] == 10.56
    assert [c["key"] for c in body["consumers"]] == ["SchB.2"]
    assert body["consumers"][0]["inputs"] > 0
    assert [h["version"] for h in body["history"]] == ["v1", "v2", "v3"]


def test_line_not_found(client):
    r = client.get("/api/lines/F1040.NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_document_detail_is_simulated_and_traced(client):
    body = client.get("/api/documents/D28").json()
    assert body["simulated"] is True
    assert body["pages"] and body["pages"][0]["printed_content"]
    assert any(v["used_by"] for v in body["values"])
    assert body["direct_lines"]


def test_document_list_hides_documents_received_after_replay_clock(client):
    now = client.get("/api/documents").json()
    everything = client.get("/api/documents?include_future=true").json()
    assert everything["total"] == 74
    assert now["total"] < everything["total"]


def test_workspace_endpoints_use_imported_packet(client):
    versions = client.get("/api/versions").json()
    assert [(v["version"], v["lines"]) for v in versions] == [("v1", 625), ("v2", 625), ("v3", 627)]
    timeline = client.get("/api/timeline?include_future=true").json()
    assert timeline["total"] == 29
    findings = client.get("/api/findings").json()
    assert findings["engine_pending"] is False
    assert "items" in findings
    scenarios = client.get("/api/scenarios").json()
    assert len(scenarios) == 5


def test_compare_versions(client):
    body = client.get("/api/compare?a=v2&b=v3").json()
    assert body["left"]["label"] == "v2" and body["right"]["label"] == "v3"
    assert body["rows"]


def test_attach_evidence_is_audited(client, fresh_workpaper):
    r = client.post("/api/evidence", headers=as_user("st-01"), json={
        "kind": "note", "title": "Call with Ngozi re: Theo SSN", "content": "Card reads 666-74-3390.",
        "attached_to": "household:theo"})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert doc_id.startswith("W-")
    detail = client.get(f"/api/documents/{doc_id}").json()
    assert detail["origin"] == "workpaper"
    assert "666-74-3390" not in detail["pages"][0]["printed_content"]
