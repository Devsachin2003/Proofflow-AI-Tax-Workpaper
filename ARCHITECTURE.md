# ProofFlow AI — Architecture

> Every number has evidence. Every decision has accountability. Every change has history.

ProofFlow is a web-native tax workpaper for one household (Okafor-Lindqvist, 2025, MFJ, CA→TX part-year).
It starts where Miraflores' extraction pipeline stops: it loads the supplied packet as an immutable baseline,
links every return number to the evidence behind it, runs checks that do not trust the engine, and layers a
human review system (findings, adjustments, notes, sign-offs, filing) on top — without ever mutating the baseline.

---

## 1. The dataset (as inspected programmatically)

| Section | Shape | Notes |
|---|---|---|
| `documents` | 74 records, 199 pages | `pages[].printed_content` = **what the paper says (truth)**. `extraction.status`: 68 extracted, 2 partial (D30/D31 page 32 unread), 4 not extracted (D07, D69, D70, D72). One `marked_corrected` (D31). |
| `extracted_values` | 3,012 | **What the pipeline read** (can be wrong). `value_type` money 1,253 / date 754 / text 474 / code 323 / … ; synthetic `position` boxes; confidence 0.41–0.99 (mean 0.98). D74 alone has 1,826 values; D23 (mileage log) 335. |
| `return_versions` | v1 (625 lines), v2 (625), v3 (627) | **What the engine computed** (can also be wrong). Each line: `key, form, line, label, value, rule, inputs[], sources[], note`. Plus `summary`, `tax_effect_rates`, `assets[]` (9), `diagnostics[]`, `changes_from_previous[]`, `carryovers_out`. 302 lines are Form 8949 lots. |
| `engine_reference` | 40 parameters, 97 rules | Rule ids referenced by every line (`R-SUM`, `R-8949-LOT`, …). |
| `prior_years` | 2024 return lines + labels + line_sources (→ D06 values), prior preparer memo/notes/open items, 6 asset records, basis records with real gaps, carryovers. |
| `tax_agency_records` | IRS transcript snapshots (2), FTB account, 2 notices, 4 e-file submissions. Some amounts are placeholders meaning "the return as your workpaper finalizes it". |
| `client` | 45 questionnaire answers, 10 messages, 1 call note. |
| `firm` | 6 staff (one without clearance, one not active until 2027), 2 client users, assignment, deadlines, budget hours, starter standards. |
| `timeline` | 29 events (2026-01-12 → 2028-01-26). v3 is dated 2026-06-23; events after that are **replayed**, not facts. |
| `what_if` | 5 alternatives (with engine results and changed lines) + the April extension estimate. |

### Reference formats found in the data (all resolvable)

| Format | Where used | Resolves to |
|---|---|---|
| `ev-NNNN` | line sources (5,846), asset sources, diagnostics, prior-year line_sources | `extracted_value` → document + page + position |
| `D01..D74` | documents_used, timeline refs, notices | `document` |
| `py:/<pointer>` | line/asset sources | JSON pointer into the stored `prior_years` baseline |
| `agency:/<pointer>` | timeline refs | JSON pointer into `tax_agency_records` |
| `asset:<id>` | line sources (54) | per-version asset, else prior-year asset record |
| `household:<id>` | line sources (18) | person record |
| `ref:param.<name>`, `ref:fx.SEK.<rate>` | line sources (39) | engine parameter |
| `timeline:<id>` | line sources (1) | timeline event |
| `qa-NN / msg-NN / call-NN` | line sources (33), diagnostics, timeline | client communications |
| `doc:<id>#page<n>` | defined by readme; not present in this packet | document page (resolver supports it) |
| line keys (`F1040.11`) | line `inputs[]` (2,042) | same-version return line |

Anything a resolver cannot find is stored with `resolved=false` and rendered as **Unresolved** — never hidden.

### Principal engineering challenges

1. **Three layers of "truth" that disagree.** Printed content vs. extracted value vs. engine line. The model keeps
   all three and makes their disagreement visible instead of picking one silently.
2. **Provenance at scale without swamping a reviewer.** ~6,000 source edges per version, 302 lots, a 335-value
   mileage log. Summary-first views, lazy expansion, and server-side pagination/filtering.
3. **Independent checks without rebuilding the engine.** Validation re-derives specific figures from evidence
   (not from engine lines) and only *asserts* errors where it can recompute deterministically; elsewhere it flags
   for human judgment.
4. **Change without loss.** Baseline is immutable; adjustments, verifications, and decisions are append-only
   overlays with full audit history, and sign-offs bind to a fingerprint of what was signed.
5. **Time.** The packet is a season. A replay clock gates which timeline events are "known" so the workpaper
   behaves correctly before and after filing (freeze, amendment, notice).

---

## 2. System architecture

```
            ┌──────────────────────────── Next.js 16 (App Router, TS strict) ───────────────────────────┐
            │ App shell (nav · command bar · version · role switcher · notifications · evidence drawer) │
            │ TanStack Query (server state) · TanStack Table/Virtual (dense views) · Recharts           │
            └───────────────▲─────────────────────────────────────────────────┬────────────────────────┘
                            │ REST/JSON (typed)        SSE /api/stream (live) │ X-Demo-User header
            ┌───────────────┴─────────────────────────────────────────────────▼────────────────────────┐
            │ FastAPI (Python 3.12) — routers per module                                                │
            │   core/       settings · demo identity · permissions · masking · errors                  │
            │   services/   import · resolver · lineage · evidence · areas · adjustments · review ·    │
            │               signoff · filing · replay · firm · audit · notifications                   │
            │   validation/ independent rule engine (pure functions over a PacketContext)              │
            │   ai/         retrieval → LLM (optional) → Pydantic-validated, citation-checked answer   │
            └───────────────▲──────────────────────────────────────────────────────────────────────────┘
                            │ SQLAlchemy 2 · Alembic
            ┌───────────────┴──────────────────────────────┐
            │ PostgreSQL 16                                │
            │  baseline schema (immutable, from packet)    │
            │  workpaper schema (append-only overlays)     │
            └──────────────────────────────────────────────┘
```

**Data flow (the trust pipeline)**

`Source records → Normalized evidence → Independent validation → Findings → Human decisions → Approved adjustments → Auditable workpaper`

The AI assistant sits *beside* this pipeline: it reads from it and drafts text, but it never writes to it.

---

## 3. Database design

Two logical groups of tables. Baseline tables are written only by the importer (idempotent upserts keyed on packet
ids); the API never updates them. Workpaper tables are the system of record for human work.

### 3.1 Baseline (immutable)

| Table | Key | Purpose |
|---|---|---|
| `packet_import` | `sha256` unique | Raw packet JSONB, file name, counts, imported_at. Re-import with the same hash is a no-op. |
| `reference_data` | `key` | Whole sections kept verbatim for JSON-pointer resolution: `prior_years`, `tax_agency_records`, `engine_reference`, `firm`, `household`, `what_if_extension`, `planning_reference_2026`, `post_filing_rates`, `fx_rates`, `readme`. |
| `person` | `id` (ngozi, erik, ada, theo) | Household members. **Sensitive columns** (`ssn`, `ip_pin`) are never returned unmasked except via the reveal endpoint. |
| `document` | `id` (D01…, and `W-0001…` for workpaper-attached evidence) | Metadata, extraction status/reason, `origin` = `packet` \| `workpaper`. |
| `document_page` | (`document_id`, `page`) | `printed_content` — rendered as the simulated page. |
| `extracted_value` | `id` (ev-NNNN) | value (JSONB) + `value_num`, type, text_as_read, x0/y0/x1/y1, confidence. FK to document page. |
| `return_version` | `version` (v1, v2, v3) | computed_at, trigger, summary, tax_effect_rates, carryovers_out, documents_used/superseded. |
| `return_line` | `id`; unique (`version`,`key`) | jurisdiction, form, line, label, value JSONB + `value_num`, rule, note, `ordinal`. |
| `line_input` | (`line_id`, `position`) | Calculation dependency edge: line → input line key (same version). Indexed on `input_key` for reverse lookup. |
| `source_ref` | `id` | **The provenance edge table.** `owner_type` (line, asset, diagnostic, timeline, prior_line), `owner_key`, `version`, `raw_ref`, `ref_type`, resolved `target_type/target_id`, `document_id`, `page`, `resolved`, `resolution_note`. Indexed on `document_id`, `target_id`. Powers both "trace a number" and "where did this document land". |
| `asset` | (`version`, `asset_id`) | 2025 per-asset depreciation (federal / CA / AMT / disposition) per version, plus `version='prior'` records. |
| `diagnostic` | `id` | Engine diagnostics per version (code, severity, message, refs). |
| `version_change` | `id` | `changes_from_previous` per version. |
| `client_item` | `id` (qa-/msg-/call-) | Questionnaire, messages, call notes — all citable evidence. |
| `timeline_event` | `id` | Ordered season events with refs. |
| `notice`, `efile_submission` | `id` | Agency notices and e-file submissions. |
| `what_if_scenario` | `id` | Five alternatives with engine results and changed lines. |
| `app_user` | `id` (st-01…, cu-01…) | Staff and client users from `firm` (role, credential, clearance, active_from). |

### 3.2 Workpaper (append-only overlays, optimistic locking via `row_version`)

| Table | Purpose |
|---|---|
| `workpaper_area` | 19 review areas (slug, title, forms/line prefixes, budget key, assigned preparer/reviewer, status). |
| `finding` | Output of the validation engine. Stable id from `rule_id + fingerprint`; category (`confirmed_error`, `suspected_discrepancy`, `needs_judgment`, `informational`), severity, blocks_filing, affected amount, estimated fed/CA effect, evidence refs, line keys, detection details, recommended action, assignee, status (`open`, `in_review`, `resolved`, `false_positive`, `accepted`), resolution note. Re-running validation never duplicates or silently reopens human-resolved findings. |
| `verification` | How a number was verified: target (line/ev/document), method (from firm `verification_types`), note, evidence refs, actor, time, `superseded_by`. |
| `adjustment` | Proposed correction to a line in the active base version: original value, proposed value, delta, tax category, estimated fed/CA effect (from `tax_effect_rates`), reason, evidence refs, finding link, status (`draft → submitted → approved/rejected → reversed`), `requires_partner`, preparer, approver, `reverses_id`, `batch_id`. |
| `workpaper_revision` | Named snapshot (R1, R2, …): base version + set of approved adjustments at a point in time, with estimated summary. Used for version comparison and filing. |
| `review_note` | Review notes, judgment calls, elections, due diligence, penalty decisions. `kind`, `blocking`, `authority` (required for judgment calls), target, status, author, assignee, due. Open blocking notes block filing. |
| `comment` | Threads on any target. `kind` = internal \| client_question; client answers become evidence. |
| `assignment` | Area/task assignment with due date and status. |
| `signoff` | Level (`preparer`, `reviewer`, `partner`, `client_approval`, `efile_authorization`), scope (area or return), signer, `fingerprint` of the signed content, status (`active`/`invalidated`), invalidation reason. |
| `filing_record` | Extension, original, amendment per jurisdiction; status (`ready`, `submitted`, `rejected`, `accepted`), frozen `snapshot` JSONB + hash, submission id, errors, `parent_id` (amendments). |
| `time_entry` | Hours per user/area (vs `firm.budget_hours`). |
| `firm_setting` | Editable standards (seeded from `starter_standards`), versioned. |
| `audit_event` | **Append-only** (DB trigger rejects UPDATE/DELETE). actor, role, action, entity, before/after, reason. |
| `sensitive_access_log` | Every unmasked view: who, which field, which record, why. |
| `notification` | Per-user notifications with links. |
| `user_seen` | Last audit id seen per user → "what changed since I last looked". |
| `replay_state` | Simulated clock (`now`) for timeline replay. |
| `ai_response` | Stored assistant outputs (question, answer, citations, validation result, model) — separate from facts. |

### 3.3 Key relationships

- `return_line 1─* line_input *─1 return_line` (dependency DAG within a version).
- `return_line 1─* source_ref *─1 extracted_value *─1 document_page *─1 document` (provenance, many-to-many).
- Reverse trace: `document → source_ref (by document_id) → owner lines` plus `→ lines that consume those lines` (transitive via `line_input`).
- `finding *─* return_line` (line keys), `finding *─* evidence` (refs), `adjustment *─1 finding`.
- `signoff → fingerprint(area)`: hash of the area's line values (base + approved adjustments), evidence attached to the area, and status of its blocking findings. When the hash changes, active sign-offs are invalidated with a recorded reason.

---

## 4. API design (REST, typed with Pydantic)

All endpoints are under `/api`. Identity for the demo is the `X-Demo-User` header (e.g. `st-02`), resolved
server-side to a user and role; permissions are checked in the service layer, not the UI.

| Area | Endpoints (abridged) |
|---|---|
| Health | `GET /health`, `GET /api/meta` (counts, replay clock, active version) |
| Identity | `GET /api/users`, `GET /api/me` |
| Overview | `GET /api/overview` (summary v3 vs prior year, readiness, queues) |
| Evidence | `GET /api/documents` (filters), `GET /api/documents/{id}` (pages, values, usage, unused reason), `GET /api/extracted-values/{id}`, `POST /api/evidence` (attach file/message/note) |
| Lineage | `GET /api/versions`, `GET /api/lines?version&form&q`, `GET /api/lines/{key}?version` (inputs, consumers, sources resolved, cross-version history, adjustments, verifications, findings), `GET /api/resolve?ref=` |
| Validation | `POST /api/validation/run`, `GET /api/findings`, `GET /api/findings/{id}`, `PATCH /api/findings/{id}` (status/assignee, optimistic lock), `POST /api/findings/bulk` |
| Adjustments | `GET/POST /api/adjustments`, `POST /api/adjustments/{id}/submit|approve|reject|reverse`, `POST /api/adjustments/bulk` |
| Versions | `GET /api/compare?a=v1&b=v3` (incl. revisions), `GET /api/revisions`, `POST /api/revisions` |
| Scenarios | `GET /api/scenarios`, `GET /api/scenarios/{id}` |
| Review | `GET/POST /api/notes`, `PATCH /api/notes/{id}`, `GET/POST /api/comments`, `GET/POST /api/assignments`, `GET/POST /api/signoffs` |
| Filing | `GET /api/filing/readiness`, `POST /api/filing/submit`, `POST /api/filing/amend`, `GET /api/filing/records` |
| Timeline | `GET /api/timeline`, `POST /api/replay/advance|reset|seek` |
| Notices | `GET /api/notices`, `GET /api/notices/{id}/package` |
| Firm | `GET /api/firm/staff`, `GET/PUT /api/firm/settings/{key}`, `GET /api/firm/access-logs`, `GET/POST /api/time` |
| Sensitive | `POST /api/sensitive/reveal` (clearance required, logged) |
| Activity | `GET /api/activity?since=`, `GET /api/stream` (SSE), `GET /api/notifications` |
| AI | `POST /api/assistant/ask` |

Errors use a uniform envelope `{error: {code, message, details}}`; 403 for permission, 409 for optimistic-lock or
state conflicts, 422 for validation.

---

## 5. Evidence-tracing model

1. **Import** parses every reference string with a single `resolver` (the same code serves the API) and stores the
   resolved edge in `source_ref`.
2. **Trace a number**: `GET /lines/{key}` returns the line, its rule text (from `engine_reference.rules`), its
   inputs (recursively expandable, lazily), and its sources, each resolved to a document, page and position.
   The UI opens the simulated page with the field highlighted.
3. **Trace a document**: `GET /documents/{id}` returns every extracted value and, per value, the lines that cite it
   in the selected version, plus the downstream lines (transitive consumers, capped and expandable). Documents not
   cited by any v3 line get an explicit reason: superseded (`documents_superseded`), duplicate image, not extracted
   (with the pipeline's reason), received after the version was computed, or "used by engine but no line cites
   it" — or **unexplained**, which itself becomes a finding.
4. **Simulated documents**: pages render `printed_content` on a normalized page canvas with a "Simulated preview —
   not an original scan" banner; `position` boxes become highlights. The viewer takes a `DocumentRenderer`
   interface so a real PDF/image renderer can replace it without touching the tracing links (links are by
   `document_id + page + bbox`, which is what a real renderer would use).

---

## 6. Independent validation engine

`backend/app/validation/` is a registry of small, pure rule functions:

```python
@rule("DUP-INCOME", area="interest-dividends", title="Same income reported by two documents")
def duplicate_income(ctx: PacketContext) -> list[FindingDraft]: ...
```

`PacketContext` gives read-only access to documents, pages, extracted values, lines (by version), prior years,
agency records, client items and parameters. Rules **do not read engine conclusions as truth**; they re-derive the
figure from printed content / extracted values / third-party records and compare. Each `FindingDraft` carries:
description, severity, category, detection rule, affected amount, evidence refs, line keys, confidence
(`deterministic` vs `heuristic`), estimated tax effect (delta × `tax_effect_rates` of the active version, labelled
as an estimate), recommended action, and a stable fingerprint.

Rule families (20): duplicate income · extracted-vs-printed mismatch · arithmetic (R-SUM/R-CARRY recompute) ·
cross-document consistency (duplicate images, corrected forms, summary vs detail) · prior-year identity · FX rate
year · superseded/corrected documents · missing basis (supplemental statements, crypto) · business income
reconciliation (1099s vs books vs return) · depreciation (bonus eligibility, repair-vs-improvement, CA/AMT
differences, prior accumulated) · S-corp basis history · carryovers vs prior return · federal/CA allocation
(residency dates vs W-2 state wages, paystub split) · third-party confirmations (transcript, FTB) · payments and
withholding (designated year, questionnaire-only payments) · outstanding documentation (expected K-1s,
low-confidence reads) · due diligence (8867) · filing blockers (computed in readiness) · year-over-year variance
(firm threshold) · engine-vs-independent recomputation (interest, mortgage interest, charitable limits, SE health
insurance eligibility, home-office/vehicle business-use).

Where an automated check cannot be conclusive (e.g. HVAC repair vs improvement, crypto basis supported only by a
bank line), the finding is `needs_judgment`, not an error.

---

## 7. Review workflow and permissions

Roles come from `firm.staff` (+ client users). The permission matrix lives in `core/permissions.py` and is enforced
in services:

| Action | Preparer | Reviewer | Partner | Firm admin | Quality reviewer | Client |
|---|---|---|---|---|---|---|
| View workpaper | ✓ | ✓ | ✓ | ✓ | ✓ | client workspace only |
| Propose adjustment / verify / attach evidence | ✓ | ✓ | ✓ | – | – | attach only |
| Approve adjustment (not own; partner if any effect > $1,000) | – | ✓ | ✓ | – | – | – |
| Create review note | – | ✓ | ✓ | – | ✓ | – |
| Clear review note | – | ✓ (not if own preparer work) | ✓ | – | ✓ | – |
| Resolve finding (false positive needs reviewer+) | ✓ | ✓ | ✓ | – | – | – |
| Preparer / reviewer / partner sign-off (no self-review) | own level | own level | own level | – | – | – |
| Edit firm standards, view access logs | – | – | – | ✓ | view logs | – |
| Approve return / sign e-file authorization | – | – | – | – | – | ✓ |
| Reveal sensitive values | if cleared | if cleared | if cleared | if cleared | if cleared | own only |

Rules from `firm.starter_standards` are configurable and read at request time: variance thresholds, partner
approval threshold, required steps, verification types.

**Filing readiness** gates (all must pass): required steps, no open blocking review notes, no open blocking findings,
all area sign-offs active, reviewer + partner return sign-offs active, client approval + e-file authorization on
the current revision fingerprint, identity checks resolved.

**Lifecycle**: Intake → Preparation → Review → Client approval → Filing → Post-filing → Amendment → Next year,
derived from the replay clock + workpaper state. Filing freezes a snapshot (hash stored); further changes create an
amendment revision linked to the filed record.

**Concurrency**: `row_version` on mutable rows; writes include `expected_version`; mismatch → 409 with the
current record. Live updates via SSE that tails `audit_event` (DB-backed, works across workers), and the client
invalidates affected queries.

---

## 8. AI assistant

`POST /api/assistant/ask {question, context: {finding_id?, line_key?, document_id?}}`

1. **Retrieve** deterministic context from the DB (finding, lines, evidence values with printed snippets, versions).
2. **Answer** with the configured LLM (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`) asked for a strict JSON shape
   `{facts[{text, citations[]}], hypotheses[{text, citations[]}], suggested_steps[], draft_note}`.
3. **Validate** with Pydantic and check every citation exists in the retrieved set; uncited/unknown claims are
   dropped or downgraded to "unverified".
4. **Fallback**: with no key, a deterministic template composer builds the same structure from retrieved records.
5. Answers are stored in `ai_response`, labelled as assistant output, and can only become workpaper content by a
   human explicitly saving a note or proposing an adjustment.

---

## 9. Tax-effect estimates (stated limitation)

The engine cannot be rerun. Local changes are estimated as `delta × tax_effect_rates[category]` of the base
version (federal and CA, per dollar); credits/payments are 1:1. Every such figure is labelled **Estimate**.
Large changes can cross thresholds (e.g. SALT cap, phase-outs) — flagged in the UI. What-if results are the
engine's own numbers from `what_if.alternatives`.

---

## 10. Repository layout

```
backend/   FastAPI app (app/api, core, db, models, schemas, services, validation, ai), Alembic, tests
frontend/  Next.js app (src/app routes, components, features, hooks, lib, types), Vitest, Playwright
reference/ the case study PDF and the packet (never modified; import reads it read-only)
scripts/   dev helpers (import, reset, smoke)
docs/      submission documents
```
