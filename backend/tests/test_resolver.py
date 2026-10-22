import pytest

from app.services.context import get_resolver
from app.services.resolver import classify


@pytest.mark.parametrize("ref,kind", [
    ("ev-0960", "extracted_value"),
    ("D28", "document"),
    ("W-0001", "document"),
    ("doc:D23#page3", "document_page"),
    ("py:/return_2024/lines/F1040.1a", "prior_year"),
    ("ref:fx.SEK.2025_average", "fx_rate"),
    ("msg-10", "client_item"),
    ("household:theo", "person"),
    ("SchB.1.6", "return_line"),
    ("v2", "return_version"),
    ("nonsense ref", "unknown"),
])
def test_classify(ref, kind):
    assert classify(ref) == kind


def test_resolves_extracted_value_to_document_page(db):
    r = get_resolver(db).resolve("ev-0960", "v3")
    assert r.resolved and r.document_id == "D36" and r.page == 1 and r.value == 18450.0


def test_resolves_fx_rates_from_reference_data(db):
    res = get_resolver(db)
    assert res.resolve("ref:fx.SEK.2024_average", "v3").value == 10.56
    assert res.resolve("ref:fx.SEK.2025_average", "v3").value == 9.86


def test_page_bounds_are_enforced(db):
    res = get_resolver(db)
    assert res.resolve("doc:D23#page4", "v3").resolved
    assert not res.resolve("doc:D23#page5", "v3").resolved


def test_unknown_references_stay_visible(db):
    r = get_resolver(db).resolve("ev-9999", "v3")
    assert not r.resolved and r.note


def test_household_member(db):
    r = get_resolver(db).resolve("household:theo", "v3")
    assert r.resolved and r.target_id == "theo"
