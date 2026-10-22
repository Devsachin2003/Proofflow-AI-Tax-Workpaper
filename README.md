# ProofFlow AI — Intelligent Tax Review Workspace

Evidence-backed tax workpaper for the Okafor-Lindqvist household, tax year 2025 (Miraflores case study).

**Every number has evidence. Every decision has accountability. Every change has history.**

This is not a tax calculator, spreadsheet clone, or chatbot. It is a review system of record: printed source pages, extracted values, and engine computations are stored as three separate layers that can disagree.

## What makes it different

- Bidirectional tracing: return line → document/page/field, and document → every line that used it (or why it did not).
- Independent validation will sit beside the supplied engine, not inside it.
- Baseline packet is immutable. Adjustments, notes, and sign-offs are overlays with audit history.
- Demo role switcher is labelled as simulated identity (`X-Demo-User`). Permissions are enforced on the API.

## Stack

- Frontend: Next.js (App Router), TypeScript, Tailwind, TanStack Query
- Backend: FastAPI, SQLAlchemy 2, Alembic, Pydantic (Python 3.12 in Docker)
- Database: PostgreSQL 16 via Docker Compose

## Local development

### Prerequisites

- Docker Desktop (PostgreSQL 16 + FastAPI/Python 3.12)
- Node.js 24 and npm (frontend)

### 1. Start the API and database

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

The API waits for Postgres, runs migrations, imports the packet idempotently, then serves `http://localhost:8000`.

- Health: `GET http://localhost:8000/health`
- Meta/counts: `GET http://localhost:8000/api/meta`

Re-running compose does not duplicate the 74 documents / 3,012 extracted values. If port 8000 is already taken by an old container, stop it (`docker ps`, then `docker stop <name>`) and run `docker compose up -d` again.

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Use the role switcher in the header (Priya Raman / Daniel Ortiz / Helen Strand / …).

### Tests

```bash
docker compose exec api pytest
```

From the host, tests need `TEST_DATABASE_URL` pointing at `proofflow_test` on port 5433.

## Demo roles

Header `X-Demo-User` selects a seeded user. This is **not** production authentication.

| ID | Name | Role | Sensitive clearance |
|---|---|---|---|
| st-01 | Priya Raman | preparer | yes |
| st-02 | Daniel Ortiz | reviewer | yes |
| st-03 | Helen Strand | partner | yes |
| st-04 | Marcus Bell | preparer | no (values stay masked) |
| st-05 | Jo Kimura | firm administrator | yes |
| st-06 | Sam Adeyemi | quality reviewer | yes (active 2027) |
| cu-01 / cu-02 | Ngozi / Erik | client | own data only |

## Known limitations (Phase 1)

- Independent validation rules are not loaded yet; engine diagnostics are shown as investigation leads.
- Adjustment, sign-off, filing freeze, and AI assistant APIs are modeled in the schema but not fully wired in the UI.
- Tax-effect estimates (when adjustments land) multiply local deltas by packet `tax_effect_rates`. The engine is not rerun.
- Document pages are simulated from `printed_content`, not original scans.
- No live IRS/FTB connection.

## Architecture

See `ARCHITECTURE.md` and `docs/requirements-coverage.md`.
