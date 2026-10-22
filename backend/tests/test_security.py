import re

import pytest

from app.core.identity import CurrentUser
from app.core.masking import mask_account, mask_ssn, mask_text
from app.core.permissions import Forbidden, can, require
from tests.conftest import as_user

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _user(role: str, clearance: bool = False) -> CurrentUser:
    return CurrentUser(id="x", name="x", role=role, kind="client" if role == "client" else "staff",
                       sensitive_clearance=clearance, active_from=None, person_id=None)


def test_masking_helpers():
    assert mask_ssn("666-74-3390") == "***-**-3390"
    assert mask_account("001234567731").endswith("7731") and "1234" not in mask_account("001234567731")
    masked = mask_text("SSN 666-74-3390, account 9876543210")
    assert "666-74" not in masked and "9876543210" not in masked


def test_permission_matrix():
    assert can("preparer", "adjustment.propose")
    assert not can("preparer", "adjustment.decide")
    assert can("reviewer", "adjustment.decide")
    assert not can("client", "workpaper.view")
    assert can("firm_administrator", "firm.settings.edit")
    assert not can("partner", "firm.settings.edit")
    with pytest.raises(Forbidden):
        require(_user("quality_reviewer"), "adjustment.propose")


def test_unknown_demo_user_rejected(client):
    r = client.get("/api/me", headers=as_user("nobody"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "unknown_user"


def test_client_cannot_read_workpaper(client):
    r = client.get("/api/lines/SchB.1.6", headers=as_user("cu-01"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


@pytest.mark.parametrize("user_id", ["st-01", "st-04"])
def test_document_responses_never_contain_raw_ssns(client, user_id):
    docs = client.get("/api/documents?include_future=true", headers=as_user(user_id)).json()["items"]
    for d in docs:
        body = client.get(f"/api/documents/{d['id']}", headers=as_user(user_id)).text
        assert not SSN_RE.search(body), f"raw SSN in {d['id']} for {user_id}"


def test_resolved_references_never_contain_raw_ssns(client, db):
    from app.services.context import get_index

    idx = get_index(db)
    refs = list(idx.client_items) + [f"household:{p}" for p in idx.people] + [
        "py:/return_2024", "py:/prior_preparer_workpaper", "agency:/irs_account_transcript_2025"]
    for ref in refs:
        body = client.get("/api/resolve", params={"ref": ref}).text
        assert not SSN_RE.search(body), f"raw SSN when resolving {ref}"


def test_line_sources_never_contain_raw_ssns(client):
    lines = client.get("/api/lines?include_lots=true&limit=1000").json()["items"]
    for ln in lines:
        if ln["sources"]:
            body = client.get(f"/api/lines/{ln['key']}").text
            assert not SSN_RE.search(body), f"raw SSN in line {ln['key']}"


def test_uncleared_preparer_cannot_attach_without_permission(client):
    r = client.post("/api/evidence", headers=as_user("st-06"),
                    json={"kind": "note", "title": "QR note", "content": "text"})
    assert r.status_code == 403
