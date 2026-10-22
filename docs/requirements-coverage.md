# Requirements coverage

Every functional requirement from *Case Study: Redesign the Tax Workpaper* (PDF pages 1–3), mapped to where it is
implemented and how it is verified. Status values: **Done** (implemented and verified by the listed test or manual
check), **Partial** (works with the stated limitation), **Planned** (not yet built).

_Last updated: Phase 2 evidence tracing and the first validation engine, verified locally (2026-10-16). Pytest 49 passed. `npm run build` succeeded. Browser walk: overview → findings → Northlake duplicate → D28/D29 highlights → SchB.1.1 → reviewer decision. Adjustment, sign-off, and the remaining rule catalog are still Planned._

## Evidence

| # | Requirement (PDF) | Implementation | Module / files | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| E1 | Trace any number to its exact source | Line lineage API resolves every `sources[]` ref to document/page/bbox; viewer highlights the selected field from `?ev=` | `backend/app/services/resolver.py`, `lineage.py`; `/calculations/[key]`, `/evidence/[id]` | `test_bidirectional_trace_and_field_location`, browser on D28 `ev-0492` and D29 `ev-0538` | Partial | Playwright suite not written; previews are simulated |
| E2 | Any document to everywhere it landed (or why it didn't) | Reverse lookup over `source_ref`, usage reason, and downstream lines | `services/evidence.py` | API test plus browser: D28 feeds `SchB.1.1` and downstream `SchB.2`; D30 shows superseded | Partial | Downstream list is capped at 60 lines |
| E3 | Record how each number was verified | `verification` records with firm verification types | `services/verification.py` | API test | Planned | |
| E4 | Link related items across return, years, related returns | Cross-version line history, prior-year line mapping, related returns panel | `services/lineage.py` | API test | Partial | History on lineage page verified; related-returns panel is household-only |
| E5 | Attach any file, message or note as evidence | `POST /api/evidence` creates workpaper documents (`W-xxxx`); document page has the form | `services/evidence.py`; `/evidence/[id]` | `test_attach_evidence_is_audited`; browser saved `W-0001` on D28 | Partial | Content is stored as text in Postgres, not an object store |
| E6 | Show source document and the specific field/location | Simulated page renderer; selected box sits above the printed text | `frontend/src/app/evidence/[id]/page.tsx` | Browser: D28 highlight aria-label is the Northlake interest field | Partial | Simulated previews only (packet has no images) |

## Calculation

| # | Requirement | Implementation | Module | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| C1 | Show how any number was built | Progressive calculation tree (inputs, rule text, sources, notes) | `services/lineage.py`; `/calculations/[key]` | `test_line_detail_traces_to_evidence`, browser | Partial | Lazy expansion of large input lists not virtualized |
| C2 | Reconcile figures that should agree | Reconciliation panels (1099s↔books↔Sch C, W-2s↔1040, payments↔transcript, broker summary↔lots) | `services/reconcile.py` | unit tests | Planned | |
| C3 | Handle large detail without swamping | Summary-first; paginated/virtualized lots and mileage | `/workpaper/areas/[id]` | manual + e2e | Planned | |
| C4 | Business books to taxable income | Books-to-tax area with mapping of each books line | `services/areas.py` | unit test | Planned | |
| C5 | Split income between states | CA allocation area (residency days, wage sourcing) | `services/areas.py`, validation `CA-WAGE-SOURCE` | unit test | Planned | |
| C6 | Run checks that don't trust the engine | Deterministic rules persisted by fingerprint; rescan does not duplicate or reopen a human decision | `backend/app/validation/rules.py`, `services/findings.py` | `tests/test_validation.py` (49 passed overall); live scan stored 13 findings | Partial | Initial rule set only, not the full catalog |

## Change

| # | Requirement | Implementation | Module | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| G1 | Adjust without losing original (who, why, tax effect) | Overlay `adjustment` records; baseline untouched; rates-based estimate | `services/adjustments.py` | tests | Planned | Estimates, not engine recompute |
| G2 | See changes live; what changed since I last looked | SSE on audit stream; `user_seen` diff | `api/stream.py`, `services/activity.py` | test | Planned | |
| G3 | Compare versions | v1/v2/v3/revisions compare | `services/lineage.py` compare; `/versions` | `test_compare_versions`, browser | Partial | Workpaper revisions UI not wired |
| G4 | Try what-ifs | Five packet scenarios with engine results | `/scenarios` | `test_workspace_endpoints_use_imported_packet`, browser | Partial | Only packet scenarios have engine results |
| G5 | Act on many items at once, with undo | Bulk finding/adjustment actions with batch id + undo | `services/bulk.py` | test | Planned | |

## Judgment

| # | Requirement | Implementation | Module | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| J1 | Flag swings from last year | `YOY` on F1040.11, F1040.15, and F1040.24 using the firm 10% and $1,000 threshold | `validation/rules.py` | Live scan; informational, does not block filing | Partial | Only those three summary lines |
| J2 | Record judgment calls, elections, due diligence, penalty decisions | `review_note.kind` with mandatory authority for judgment calls | `services/review.py` | test | Planned | |
| J3 | Prove completeness: every document used, every area considered, every outside filing identified | Completeness view: document accounting, area status, outside filings (FBAR, 1099-NEC, 3520, Oregon/Arizona composites, Ada's return) | `/filing`, `services/completeness.py` | test | Planned | |

## People

| # | Requirement | Implementation | Module | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| P1 | Questions to client/colleagues that become evidence | Comment threads; answered client questions become evidence | `services/review.py` | test | Planned | |
| P2 | Review notes that can block filing | Blocking notes gate readiness | `services/filing.py` | test | Planned | |
| P3 | Sign-offs that reopen when what was signed changes | Fingerprint-bound sign-offs, auto-invalidation | `services/signoff.py` | test | Planned | |
| P4 | Enforced roles | Server-side permission matrix | `core/permissions.py` | `tests/test_security.py`, browser client 403 | Partial | Demo identity header, not production auth |
| P5 | Several people at once | Optimistic locking (409), SSE refresh | services | test | Planned | |
| P6 | Assignments, deadlines, notifications | `assignment`, firm deadlines, `notification` | `services/review.py` | test | Planned | |
| P7 | Client approval and e-file signature | Client workspace; approval + 8879 sign-off bound to revision | `/client` | test | Planned | Simulated signature |

## Filing and after

| # | Requirement | Implementation | Module | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| F1 | Extensions | Extension record from `what_if.extension` + timeline | `services/filing.py` | test | Planned | |
| F2 | Filing, e-file rejections | Simulated submissions; packet rejection replayed | `services/filing.py`, replay | test | Planned | No real IRS/FTB connection |
| F3 | Client's copy | Generated client copy view of the frozen snapshot | `/filing` | manual | Planned | |
| F4 | Freeze at filing; amend on top | Frozen snapshot + hash; amendments create linked revisions | `services/filing.py` | test | Planned | |
| F5 | Answer a notice with a self-contained record | Notice response package (items, lines, sources, history, decisions) | `/notices` | test | Planned | |
| F6 | Carry everything forward with history; plan next year | Carryforward view (carryovers_out, basis, assets, open items) + 2026 planning | `/filing` next-year tab | test | Planned | |

## Firm

| # | Requirement | Implementation | Module | Verification | Status | Limitations |
|---|---|---|---|---|---|---|
| R1 | Firm-wide standards | Editable `firm_setting` (seeded from starter_standards) | `/firm/settings` | test | Planned | |
| R2 | Protection of sensitive data with view logs | Masking in serializers; reveal endpoint with clearance + log | `core/masking.py` | `tests/test_security.py`, browser SSNs masked | Partial | Reveal-and-log endpoint not yet exposed in UI |
| R3 | Time against budget | `time_entry` vs `budget_hours` | `/firm` | test | Planned | |
| R4 | Status and search | Firm overview + command-bar search | `/firm`, search API | e2e | Planned | Single seeded household |

## Records a CPA expects

| Record | Where | Status |
|---|---|---|
| Return summary vs last year | Overview | Planned |
| Tax computation | `/calculations` (F1040 tree) | Planned |
| Area summaries | `/workpaper/areas` | Planned |
| Document index | `/evidence` | Planned |
| Depreciation by asset (method, life, bonus, fed vs CA vs AMT, disposals, recapture) | Area: depreciation | Planned |
| Sales detail | Area: capital gains (lots) | Planned |
| Books to tax | Area: books-to-tax | Planned |
| Rentals and passive losses | Areas: rental, passive | Planned |
| K-1 lines | Area: K-1s | Planned |
| Retirement and foreign items | Areas | Planned |
| Deductions and credits with limits | Areas | Planned |
| Payments | Area: payments | Planned |
| State split | Area: CA allocation | Planned |
| Carryovers | Area: carryovers | Planned |
| Basis by year | Area: basis | Planned |
| Prior preparer did vs what we changed | Area: carryovers / prior-year panel | Planned |

## Submission artifacts

| Artifact | File | Status |
|---|---|---|
| Working web app with role switcher | `frontend/`, `backend/` | Partial (Phase 2 tracing and findings verified 2026-10-16; adjustments and sign-off still open) |
| One page on core idea and data model | `docs/core-idea-and-data-model.md` | Planned |
| Errors found and how the design surfaced them | `docs/error-findings.md` | Partial (13 persisted findings from the first rule set; written from the live scan) |
| Video walkthrough outline | `docs/video-walkthrough.md` | Planned (recording by applicant) |
| AI usage disclosure | `README.md` | Planned |
