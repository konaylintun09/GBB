# Flowea Maintenance API (CMMS)

FastAPI + PostgreSQL backend for the QR-based preventive-maintenance system.
Implements the Phase 1 loop: **admin sets up equipment → engineer scans & submits → schedule recalculates → dashboards update.**

## Run it (one command)

```bash
cp .env.example .env          # already created for you in this package
docker compose up --build
```

- API:        http://localhost:8000
- Swagger UI:  http://localhost:8000/docs
- Health:      http://localhost:8000/health

Tables are created automatically on first boot and demo data is seeded (set `SEED_DEMO=false` to disable).

### Run without Docker (local dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# point DATABASE_URL at any Postgres, then:
uvicorn app.main:app --reload
```

## Demo logins (change before production)

| Role        | Email                | Password    |
|-------------|----------------------|-------------|
| Admin       | admin@flowea.io      | `flowea123` |
| Engineer    | engineer@flowea.io   | `flowea123` |
| Leadership  | lead@flowea.io       | `flowea123` |

Get a token: `POST /auth/login` → use the `access_token` as `Authorization: Bearer <token>`.

## Endpoints (Phase 1)

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/login` | public | Email + password → access & refresh tokens |
| POST | `/auth/refresh` | public | Exchange a refresh token for a new pair |
| GET  | `/auth/me` | any | Current user |
| GET  | `/equipment` | any | List equipment + schedule status |
| POST | `/equipment` | admin | Create equipment (auto tag + QR token + schedule) |
| GET  | `/equipment/{id}` | any | One asset |
| GET  | `/equipment/by-qr/{qr_token}` | any | **Scan** — resolve QR to asset + what's due |
| GET  | `/checklists?equipment_type=&frequency=` | any | Checklist template for a type + interval |
| POST | `/records` | admin, engineer | **Submit** a completed inspection (recalculates next due) |
| GET  | `/records` | admin, leadership | Inspection history (audit trail) |
| GET  | `/dashboard/summary` | any | Counts: total / due soon / overdue / completed today |
| POST | `/media/presign` | admin, engineer | Presigned upload URL (needs S3/R2 configured) |

## Data model

`users · equipment · maintenance_schedule · checklist_template · checklist_item · inspection_record · inspection_result · media`

Key decisions:
- **Frequency lives on `maintenance_schedule` (admin-owned)** — the engineer only performs what's due. Submitting a record sets `last_done` and recalculates `next_due = performed_at + frequency`.
- **QR token is an opaque value** (`FLW-...`), not a sequential id, so assets can't be enumerated.
- **`inspection_record` is an append-only audit trail.** Photos/videos are NOT stored in the DB — only an object-storage key in `media`.
- Schedule **status** (ok / due_soon / overdue) is computed at read time from `next_due`, never stored stale.

## Security notes

- Passwords hashed with **argon2**; JWT access (short-lived) + refresh tokens; role checks enforced on the API, not just the UI.
- Before production: set a strong `JWT_SECRET` (`openssl rand -hex 32`), change demo passwords, set `SEED_DEMO=false`, lock `CORS_ORIGINS` to your real front-end, and remove the `db` port mapping in `docker-compose.yml`.

## What's next (not in this scaffold)

1. **Alembic migrations** — this MVP uses `create_all` on boot; switch to migrations before real data exists.
2. **Object storage wiring** — set the `S3_*` vars (Cloudflare R2 or AWS S3) to enable `/media/presign`; the front-end uploads directly to the bucket.
3. **Notifications** — daily job to flag due-soon / overdue and alert via email/Telegram (in-app scheduler or n8n).
4. **Connect the front-end** — point the React demo's data calls at this API (`/auth/login`, `/equipment`, `/equipment/by-qr/...`, `/checklists`, `/records`, `/dashboard/summary`).
5. **Tests + CI** — GitHub Actions: lint, test, build image, push to GHCR, deploy.

## Project layout

```
app/
  main.py        app entry (lifespan: init_db + seed)
  config.py      settings from .env
  database.py    async engine + session + Base
  models.py      ORM tables (the schema)
  schemas.py     Pydantic request/response models
  security.py    argon2 + JWT
  deps.py        auth + role guards (RBAC)
  util.py        date/status helpers
  seed.py        demo data
  routers/       auth · equipment · checklists · records · dashboard · media
docker-compose.yml · Dockerfile · requirements.txt · .env.example
```
