"""Deterministic checks over the immutable packet. They do not trust engine totals as truth
and they never write to return lines.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.services.packet_index import PacketIndex
from app.validation.types import FindingDraft, fingerprint

_NUM = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z]{4,}")
_STOP = {"interest", "ordinary", "dividends", "total", "bank", "form", "income", "north", "composite"}


def run_rules(idx: PacketIndex, version: str | None = None) -> list[FindingDraft]:
    version = version or idx.current_version
    drafts: list[FindingDraft] = []
    drafts.extend(duplicate_income(idx, version))
    drafts.extend(printed_source_mismatches(idx))
    drafts.extend(foreign_exchange(idx, version))
    drafts.extend(identity_mismatches(idx))
    drafts.extend(arithmetic_checks(idx, version))
    drafts.extend(missing_cost_basis(idx, version))
    drafts.extend(superseded_conflicts(idx, version))
    drafts.extend(year_over_year(idx, version))
    drafts.extend(missing_evidence(idx, version))
    return drafts


def _nums(text: str) -> set[float]:
    out: set[float] = set()
    for m in _NUM.finditer(text or ""):
        try:
            out.add(round(float(m.group().replace(",", "")), 2))
        except ValueError:
            continue
    return out


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD.findall(text or "")} - _STOP


def duplicate_income(idx: PacketIndex, version: str) -> list[FindingDraft]:
    """Same dollar amount reported on two payer lines whose issuers or labels overlap."""
    lines = idx.lines[version]
    groups: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for ln in lines.values():
        if ln["rule"] not in ("R-INTEREST-PAYER", "R-DIVIDEND-PAYER"):
            continue
        ev_ids = [s for s in ln.get("sources") or [] if s.startswith("ev-")]
        if len(ev_ids) != 1 or ev_ids[0] not in idx.ev:
            continue
        ev = idx.ev[ev_ids[0]]
        if not isinstance(ev.get("value"), (int, float)):
            continue
        doc = idx.documents[ev["document_id"]]
        groups[(ln["rule"], round(float(ev["value"]), 2))].append(
            {"line": ln, "ev": ev, "doc": doc}
        )
    out = []
    for (rule, amount), items in groups.items():
        if len(items) < 2 or amount == 0:
            continue
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                if a["doc"]["id"] == b["doc"]["id"]:
                    continue
                shared = (_tokens(a["doc"].get("issuer") or "") & _tokens(b["doc"].get("issuer") or "")) or (
                    _tokens(a["line"]["label"]) & _tokens(b["line"]["label"])
                )
                if not shared:
                    continue
                kind = "interest" if rule == "R-INTEREST-PAYER" else "dividend"
                fp = fingerprint("DUP-INCOME", version, rule, amount, a["ev"]["id"], b["ev"]["id"])
                out.append(FindingDraft(
                    rule_id="DUP-INCOME",
                    fingerprint=fp,
                    title=f"Possible duplicate {kind}: ${amount:,.0f}",
                    description=(
                        f"{a['line']['key']} ({a['doc']['id']} {a['doc'].get('issuer')}) and "
                        f"{b['line']['key']} ({b['doc']['id']} {b['doc'].get('issuer')}) both report "
                        f"${amount:,.2f}. The issuers or labels overlap ({', '.join(sorted(shared))}). "
                        "This is a suspected duplicate until a reviewer confirms the amounts are distinct."
                    ),
                    category="suspected_discrepancy",
                    severity="warning",
                    blocks_filing=True,
                    area_id="interest-dividends",
                    affected_amount=amount,
                    tax_category="interest" if kind == "interest" else "interest",
                    tax_delta=-amount,
                    evidence=[a["ev"]["id"], b["ev"]["id"], a["doc"]["id"], b["doc"]["id"]],
                    line_keys=[a["line"]["key"], b["line"]["key"]],
                    recommended_action="Open both source fields. If one statement already includes the other, remove the duplicate payer line. Do not change the return until a reviewer approves.",
                    details={
                        "amount": amount,
                        "pairs": [
                            {"line": a["line"]["key"], "document_id": a["doc"]["id"], "ev": a["ev"]["id"],
                             "page": a["ev"]["page"], "label": a["ev"]["label"], "value": a["ev"]["value"]},
                            {"line": b["line"]["key"], "document_id": b["doc"]["id"], "ev": b["ev"]["id"],
                             "page": b["ev"]["page"], "label": b["ev"]["label"], "value": b["ev"]["value"]},
                        ],
                    },
                ))
    return out


def printed_source_mismatches(idx: PacketIndex) -> list[FindingDraft]:
    """Extracted money that does not appear as a number on the printed page. Zeros are ignored."""
    out = []
    for ev in idx.ev.values():
        if ev.get("value_type") != "money" or not isinstance(ev.get("value"), (int, float)):
            continue
        val = round(float(ev["value"]), 2)
        if val == 0:
            continue
        page = idx.page_text(ev["document_id"], ev["page"])
        if val in _nums(page):
            continue
        fp = fingerprint("EXTRACT-PRINTED", ev["id"])
        out.append(FindingDraft(
            rule_id="EXTRACT-PRINTED",
            fingerprint=fp,
            title=f"Extracted amount not on printed page ({ev['id']})",
            description=(
                f"{ev['id']} on {ev['document_id']} page {ev['page']} was read as {val:,.2f} "
                f"(text_as_read {ev.get('text_as_read')!r}, confidence {ev.get('confidence')}). "
                "That number is not present in printed_content."
            ),
            category="suspected_discrepancy",
            severity="warning",
            blocks_filing=True,
            area_id="itemized-deductions" if ev["document_id"] == "D64" else None,
            affected_amount=val,
            evidence=[ev["id"], ev["document_id"]],
            recommended_action="Compare the highlight to the printed sentence and record the digit a reviewer can actually read.",
            confidence="deterministic",
            details={"value": ev["value"], "text_as_read": ev.get("text_as_read"), "page": ev["page"],
                     "field": ev["field"], "label": ev["label"], "printed_excerpt": page[:400]},
        ))
    return out


def foreign_exchange(idx: PacketIndex, version: str) -> list[FindingDraft]:
    """A line cites an FX rate whose year is not the return year, while that year's rate exists."""
    tax_year = int(idx.raw["household"]["tax_year"])
    fx = ((idx.params.get("fx") or {}).get("SEK") or {})
    out = []
    for ln in idx.lines[version].values():
        for ref in ln.get("sources") or []:
            m = re.fullmatch(r"ref:fx\.SEK\.((20\d{2})_[A-Za-z0-9_]+)", ref)
            if not m:
                continue
            rate_name, rate_year_s = m.group(1), m.group(2)
            rate_year = int(rate_year_s)
            if rate_year == tax_year:
                continue
            kind = rate_name.split("_", 1)[1]  # average | year_end
            current_name = f"{tax_year}_{kind}"
            if current_name not in fx or rate_name not in fx:
                continue
            used = float(fx[rate_name])
            current = float(fx[current_name])
            sek = None
            for src in ln.get("sources") or []:
                if src.startswith("ev-") and isinstance(idx.ev[src].get("value"), (int, float)):
                    sek = float(idx.ev[src]["value"])
            engine = float(ln["value"]) if isinstance(ln["value"], (int, float)) else None
            independent = round(sek / current) if sek else None
            delta = None if independent is None or engine is None else independent - engine
            fp = fingerprint("FX-YEAR", version, ln["key"], ref, current_name)
            out.append(FindingDraft(
                rule_id="FX-YEAR",
                fingerprint=fp,
                title=f"FX rate year mismatch on {ln['key']}",
                description=(
                    f"{ln['key']} cites {ref} ({used} SEK per USD, year {rate_year}) for tax year {tax_year}. "
                    f"engine_reference also has {current_name} = {current}. "
                    + (f"SEK {sek:,.2f} / {current} ≈ {independent} USD; the engine stored {engine}." if sek else "")
                ),
                category="confirmed_error",
                severity="error",
                blocks_filing=True,
                area_id="foreign",
                affected_amount=None if delta is None else abs(delta),
                tax_category="interest",
                tax_delta=delta,
                evidence=[ref] + [s for s in ln.get("sources") or [] if s.startswith("ev-")],
                line_keys=[ln["key"]],
                recommended_action=f"Recompute with ref:fx.SEK.{current_name} unless a reviewer documents why the {rate_year} rate applies.",
                details={"used_rate": used, "current_year_rate": current, "rate_name": rate_name,
                         "current_name": current_name, "sek": sek, "engine_usd": engine,
                         "independent_usd": independent, "label": ln["label"]},
            ))
    return out


def identity_mismatches(idx: PacketIndex) -> list[FindingDraft]:
    """Household SSN versus prior-year dependent SSN for the same name, plus supporting extracts."""
    prior = {d["name"].strip().lower(): d for d in idx.prior_years["return_2024"].get("dependents") or []}
    out = []
    for person in idx.raw["household"]["people"]:
        key = person["name"].strip().lower()
        prev = prior.get(key)
        if not prev or not person.get("ssn") or not prev.get("ssn"):
            continue
        if person["ssn"] == prev["ssn"]:
            continue
        support = [e["id"] for e in idx.ev.values()
                   if e.get("value_type") == "ssn" and e.get("value") in (person["ssn"], prev["ssn"])]
        fp = fingerprint("IDENTITY-SSN", person["id"], person["ssn"], prev["ssn"])
        out.append(FindingDraft(
            rule_id="IDENTITY-SSN",
            fingerprint=fp,
            title=f"SSN mismatch for {person['name']}",
            description=(
                f"Household record {person['id']} has SSN ending {person['ssn'][-4:]}; "
                f"the 2024 return dependent record ends {prev['ssn'][-4:]}. "
                "Extracted identity fields that match either value are linked. This needs human confirmation; "
                "it is not treated as a computed tax error."
            ),
            category="needs_judgment",
            severity="warning",
            blocks_filing=True,
            area_id="carryovers",
            tax_category="none",
            tax_delta=0,
            evidence=["household:" + person["id"], "py:/return_2024/dependents", *support],
            recommended_action="Compare the Social Security card and the prior-year return. Record which SSN is correct. Do not file until identity is confirmed.",
            confidence="deterministic",
            details={"person_id": person["id"], "name": person["name"],
                     "current_ssn_last4": person["ssn"][-4:], "prior_ssn_last4": prev["ssn"][-4:],
                     "supporting_values": support},
        ))
    return out


def arithmetic_checks(idx: PacketIndex, version: str) -> list[FindingDraft]:
    lines = idx.lines[version]
    out = []
    for ln in lines.values():
        if ln["rule"] == "R-CARRY":
            vals = _numeric_inputs(lines, ln)
            if len(vals) == 1 and isinstance(ln["value"], (int, float)) and abs(vals[0] - float(ln["value"])) > 1:
                out.append(_arith_draft(version, ln, vals, "carry"))
        elif ln["rule"] == "R-SUM":
            vals = _numeric_inputs(lines, ln)
            if len(vals) < 2 or not isinstance(ln["value"], (int, float)):
                continue
            target = float(ln["value"])
            total = sum(vals)
            diff = vals[0] - sum(vals[1:])
            if min(abs(total - target), abs(diff - target), abs(abs(diff) - abs(target))) > 1:
                out.append(_arith_draft(version, ln, vals, "sum"))
    out.extend(_broker_summary(idx, version))
    return out


def _numeric_inputs(lines: dict[str, dict], ln: dict) -> list[float]:
    vals = []
    for key in ln.get("inputs") or []:
        other = lines.get(key)
        if not other or not isinstance(other.get("value"), (int, float)):
            return []
        vals.append(float(other["value"]))
    return vals


def _arith_draft(version: str, ln: dict, vals: list[float], kind: str) -> FindingDraft:
    fp = fingerprint("ARITH", version, ln["key"], kind)
    return FindingDraft(
        rule_id="ARITH",
        fingerprint=fp,
        title=f"Arithmetic check failed for {ln['key']}",
        description=f"{ln['key']} ({ln['label']}) is {ln['value']} under {ln['rule']}, which does not match its inputs {vals}.",
        category="confirmed_error",
        severity="error",
        blocks_filing=True,
        line_keys=[ln["key"], *(ln.get("inputs") or [])],
        affected_amount=abs(float(ln["value"])) if isinstance(ln["value"], (int, float)) else None,
        recommended_action="Recompute the line from its inputs before relying on it.",
        details={"inputs": ln.get("inputs"), "input_values": vals, "rule": ln["rule"]},
    )


def _broker_summary(idx: PacketIndex, version: str) -> list[FindingDraft]:
    superseded = set(idx.versions[version].get("documents_superseded") or [])
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for ev in idx.ev.values():
        by_doc[ev["document_id"]].append(ev)
    out = []
    for doc_id, rows in by_doc.items():
        if doc_id in superseded:
            continue
        summary = next((e for e in rows if e["field"] == "b_summary_proceeds" and isinstance(e.get("value"), (int, float))), None)
        lots = [e for e in rows if str(e["field"]).endswith("_proceeds") and e["field"] != "b_summary_proceeds"
                and isinstance(e.get("value"), (int, float))]
        if not summary or len(lots) < 2:
            continue
        total = round(sum(float(e["value"]) for e in lots), 2)
        stated = round(float(summary["value"]), 2)
        if abs(total - stated) <= 1:
            continue
        fp = fingerprint("ARITH-BROKER", version, doc_id, summary["id"])
        out.append(FindingDraft(
            rule_id="ARITH-BROKER",
            fingerprint=fp,
            title=f"Broker summary proceeds disagree with lots ({doc_id})",
            description=(
                f"{doc_id} summary proceeds {summary['id']} are {stated:,.2f}. "
                f"The sum of {len(lots)} extracted lot proceeds is {total:,.2f} (difference {stated - total:,.2f})."
            ),
            category="suspected_discrepancy",
            severity="warning",
            blocks_filing=True,
            area_id="capital-gains",
            affected_amount=abs(stated - total),
            tax_category="stcg",
            tax_delta=total - stated,
            evidence=[summary["id"], doc_id, *[e["id"] for e in lots[:8]]],
            recommended_action="Tie the 1099-B summary to the lot detail before using either figure.",
            details={"summary": stated, "lot_sum": total, "lot_count": len(lots)},
        ))
    return out


def missing_cost_basis(idx: PacketIndex, version: str) -> list[FindingDraft]:
    out = []
    for ev in idx.ev.values():
        label = f"{ev.get('field', '')} {ev.get('label', '')}".lower()
        if "basis" not in label or ev.get("value") not in (None, ""):
            continue
        users = [ln["key"] for ln in idx.lines[version].values() if ev["id"] in (ln.get("sources") or [])]
        fp = fingerprint("MISSING-BASIS", ev["id"])
        out.append(FindingDraft(
            rule_id="MISSING-BASIS",
            fingerprint=fp,
            title=f"Missing cost basis ({ev['id']})",
            description=(
                f"{ev['label']} on {ev['document_id']} ({ev['id']}) has no extracted amount "
                f"(confidence {ev.get('confidence')}). "
                + (f"Return lines citing it: {', '.join(users)}." if users else "No return line cites it directly.")
            ),
            category="needs_judgment",
            severity="warning",
            blocks_filing=True,
            area_id="digital-assets",
            evidence=[ev["id"], ev["document_id"]],
            line_keys=users,
            recommended_action="Obtain basis from the transfer records. Do not assume zero basis is correct.",
            confidence="heuristic",
            details={"confidence": ev.get("confidence"), "field": ev["field"]},
        ))
    return out


def superseded_conflicts(idx: PacketIndex, version: str) -> list[FindingDraft]:
    v = idx.versions[version]
    superseded = set(v.get("documents_superseded") or [])
    corrected = [d for d in idx.documents.values() if d.get("marked_corrected")]
    out = []
    for new in corrected:
        old = next((d for d in idx.documents.values()
                    if d["id"] != new["id"] and d["id"] in superseded and d.get("issuer") == new.get("issuer")
                    and d.get("document_type") == new.get("document_type")), None)
        if not old:
            continue
        old_f = {e["field"]: e for e in idx.ev_by_doc.get(old["id"], [])}
        new_f = {e["field"]: e for e in idx.ev_by_doc.get(new["id"], [])}
        diffs = []
        for field, a in old_f.items():
            b = new_f.get(field)
            if b and a.get("value") != b.get("value"):
                diffs.append({"field": field, "label": a.get("label"), "superseded": a.get("value"),
                              "corrected": b.get("value"), "superseded_ev": a["id"], "corrected_ev": b["id"]})
        old_ids = {e["id"] for e in old_f.values()}
        cited = [ln["key"] for ln in idx.lines[version].values() if old_ids & set(ln.get("sources") or [])]
        fp = fingerprint("SUPERSEDED", version, old["id"], new["id"])
        out.append(FindingDraft(
            rule_id="SUPERSEDED",
            fingerprint=fp,
            title=f"{old['id']} superseded by corrected {new['id']}",
            description=(
                f"{old['title']} is in documents_superseded. {new['id']} is marked corrected. "
                f"{len(diffs)} shared fields differ. "
                + ("Current-version lines still cite the superseded document: " + ", ".join(cited) + "."
                   if cited else "No current-version line cites the superseded document.")
            ),
            category="suspected_discrepancy" if diffs else "informational",
            severity="warning" if diffs or cited else "info",
            blocks_filing=bool(cited),
            area_id="capital-gains",
            evidence=[old["id"], new["id"], *[d["corrected_ev"] for d in diffs[:6]], *[d["superseded_ev"] for d in diffs[:6]]],
            line_keys=cited[:12],
            affected_amount=None,
            recommended_action="Use the corrected document. Confirm every changed field is the one on the return.",
            details={"differences": diffs[:20], "still_cited": cited},
        ))
    return out


def year_over_year(idx: PacketIndex, version: str) -> list[FindingDraft]:
    std = idx.raw["firm"]["starter_standards"]["variance_review"]
    pct_lim = float(std["flag_if_change_over_percent"])
    amt_lim = float(std["and_over_amount"])
    prior = idx.prior_years["return_2024"]["lines"]
    labels = idx.prior_years["return_2024"].get("line_labels") or {}
    keys = ("F1040.11", "F1040.15", "F1040.24")
    out = []
    for key in keys:
        cur = idx.line(version, key)
        if not cur or key not in prior:
            continue
        if not isinstance(cur["value"], (int, float)) or not isinstance(prior[key], (int, float)):
            continue
        old, new = float(prior[key]), float(cur["value"])
        delta = new - old
        pct = None if old == 0 else abs(delta) / abs(old) * 100
        if abs(delta) <= amt_lim or pct is None or pct <= pct_lim:
            continue
        fp = fingerprint("YOY", version, key)
        out.append(FindingDraft(
            rule_id="YOY",
            fingerprint=fp,
            title=f"Large year-over-year change on {key}",
            description=(
                f"{cur['label']} is {new:,.0f} in {version} versus {old:,.0f} in 2024 "
                f"({delta:+,.0f}, {pct:.1f}%). Firm threshold is {pct_lim:.0f}% and ${amt_lim:,.0f}."
            ),
            category="informational",
            severity="info",
            blocks_filing=False,
            area_id="tax-computation",
            affected_amount=abs(delta),
            evidence=["py:/return_2024/lines/" + key],
            line_keys=[key],
            recommended_action="Explain the swing in the workpaper. This is a review flag, not an error by itself.",
            confidence="deterministic",
            details={"prior": old, "current": new, "percent": round(pct, 1), "prior_label": labels.get(key)},
        ))
    return out


def missing_evidence(idx: PacketIndex, version: str) -> list[FindingDraft]:
    """Low-confidence reads and partial extractions that still need a human source."""
    out = []
    threshold = 0.8
    for ev in idx.ev.values():
        conf = float(ev.get("confidence") or 0)
        if conf >= threshold:
            continue
        fp = fingerprint("LOW-CONFIDENCE", ev["id"])
        users = [ln["key"] for ln in idx.lines[version].values() if ev["id"] in (ln.get("sources") or [])]
        out.append(FindingDraft(
            rule_id="LOW-CONFIDENCE",
            fingerprint=fp,
            title=f"Low-confidence read {ev['id']} ({conf:.2f})",
            description=(
                f"{ev['label']} on {ev['document_id']} was read as {ev.get('value')!r} "
                f"with confidence {conf:.2f}, below {threshold:.2f}."
            ),
            category="needs_judgment",
            severity="warning",
            blocks_filing=True,
            evidence=[ev["id"], ev["document_id"]],
            line_keys=users,
            recommended_action="Re-read the printed field and attach a reviewer note. Do not treat the extract as verified.",
            confidence="heuristic",
            details={"confidence": conf, "value": ev.get("value"), "text_as_read": ev.get("text_as_read"),
                     "page": ev["page"]},
        ))
    for doc in idx.documents.values():
        status = (doc.get("extraction") or {}).get("status")
        if status != "partial":
            continue
        if doc["id"] in set(idx.versions[version].get("documents_superseded") or []):
            continue
        fp = fingerprint("PARTIAL-EXTRACT", doc["id"])
        out.append(FindingDraft(
            rule_id="PARTIAL-EXTRACT",
            fingerprint=fp,
            title=f"Partial extraction on {doc['id']}",
            description=f"{doc['title']}: {(doc.get('extraction') or {}).get('reason')}",
            category="needs_judgment",
            severity="warning",
            blocks_filing=False,
            evidence=[doc["id"]],
            recommended_action="Read the unextracted pages before signing the area that uses this document.",
            confidence="heuristic",
            details={"reason": (doc.get("extraction") or {}).get("reason")},
        ))
    return out
