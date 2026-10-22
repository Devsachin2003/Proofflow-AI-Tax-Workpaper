# Implementation progress

_Last updated: Phase 2 evidence tracing and first validation engine, verified locally (2026-10-16)._

## Dataset

Unchanged from the Phase 1 import. 74 packet documents, 199 pages, 3,012 extracted values, return lines v1 625 / v2 625 / v3 627. The packet file and baseline rows were not edited.

A browser review also saved one workpaper note, `W-0001`, attached to D28. That row is origin `workpaper`.

## What Phase 2 added

- Document viewer highlights the selected extracted field. Lineage links open `/evidence/{doc}?ev=&page=`. The field list links back to the return lines, and the page lists downstream calculations plus why the document is used, unused, corrected, or superseded.
- Notes, messages, and file descriptions can be saved from the document page. They become `W-xxxx` documents. The packet JSON is left as imported.
- `run_validation()` runs reusable rules and upserts findings by fingerprint. A repeat scan does not insert duplicates and does not reopen `resolved`, `false_positive`, or `accepted` rows.
- `/findings` and `/findings/[id]` show the stored finding, its rule, sources, lines, estimate, notes, and audit history. Verified maps to `resolved`. Unresolved maps to `open`. False positive requires a reviewer or partner. Decisions do not change return values.

## Findings from the live scan

13 findings on v3. Details are in `docs/error-findings.md`.

The three requested examples were produced by rules:

- `DUP-INCOME` `F-031217325d`: D28 `ev-0492` and D29 `ev-0538`, both $1,840, lines `SchB.1.1` and `SchB.1.2`.
- `FX-YEAR` `F-aed7922bdc`: `SchB.1.6` uses 2024 SEK/USD 10.56; 2025 average is 9.86; independent USD 1,871 versus engine 1,747.
- `IDENTITY-SSN` `F-55c012a127`: Theo household ending 3309 versus prior-year ending 3390, with `ev-0012` and `ev-1080`.

## Verification

```
docker compose exec -T api pytest
# 49 passed, 0 failed, 0 skipped

cd frontend && npm run build
# Next.js 16.4.1 compiled; TypeScript finished; 20 routes generated
```

Browser, signed in first as Priya Raman then Daniel Ortiz:

1. Overview priority queue lists the duplicate-interest finding from the database.
2. `/findings` lists the 13 stored findings.
3. The Northlake finding links to D28 `ev-0492` and D29 `ev-0538`.
4. Both document pages highlight the interest field. D28 shows downstream `SchB.2` at $6,450.
5. `SchB.1.1` still shows $1,840 and links back to D28 page 1.
6. A preparer false-positive click returned a permission error. Daniel Ortiz marked the finding verified. Audit history shows `finding.decide` by `st-02`. A second scan reported `created: 0`, `preserved: 1`, and the status stayed `resolved`.
7. The attach form saved `W-0001`.

## Still incomplete

- The rest of the planned rule catalog (wage sourcing, books-to-tax, payments versus transcript, and the other area checks) is not loaded.
- Adjustments, sign-offs, filing mutations, and the top search box are still placeholders.
- No Playwright or Vitest suite.
- Previews are simulated from `printed_content`.
- Demo identity is still the `X-Demo-User` header.

Do not treat this as a finished product. The tracing path and the first source-linked validation scan are tested. Later review workflows are not.
