# Endo EMR Migration Guide

This document describes how to run the new React + FastAPI stack alongside the legacy Flask EMR and cut over when ready.

## Architecture

| Component | Location | Port |
|-----------|----------|------|
| Legacy Flask EMR | `modern-EMR-main/` | 5000 |
| FastAPI backend | `backend/` | 8000 |
| React frontend | `frontend/` | 5173 |
| PostgreSQL | Docker | 5432 |

## Quick Start (Docker)

```bash
cd "MyEMR - Copy"
docker compose up --build
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Demo login: `demo@clinic.com` / `password123`

## Local Development (without Docker)

### PostgreSQL

Install PostgreSQL and create database:

```sql
CREATE USER emr WITH PASSWORD 'emr_secret';
CREATE DATABASE endo_emr OWNER emr;
```

### Backend

```bash
cd backend
pip install -r requirements.txt
set DATABASE_URL=postgresql://emr:emr_secret@localhost:5432/endo_emr
set SEED_ON_STARTUP=true
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` in `frontend/.env` if not using Vite proxy.

## Migrate SQLite Data from Flask

After the Flask app has populated `modern-EMR-main/instance/emr.db`:

```bash
# Dry run (counts only)
python scripts/migrate_sqlite_to_pg.py --dry-run

# Full migration
set DATABASE_URL=postgresql://emr:emr_secret@localhost:5432/endo_emr
python scripts/migrate_sqlite_to_pg.py
```

The script truncates PostgreSQL tables and re-imports all rows, preserving relationships via ID remapping.

## Cutover Checklist

1. **Parity testing** — Complete a full workflow in React:
   - Login → Register patient → New visit → Prescribe → PDF download
2. **Data migration** — Run `migrate_sqlite_to_pg.py` and verify row counts match
3. **PDF comparison** — Generate PDF for same visit in Flask and FastAPI; compare output
4. **Drug warnings** — Prescribe Metformin for patient with CKD comorbidity; confirm warning appears
5. **Backup** — Export PostgreSQL dump before switching production traffic
6. **DNS / routing** — Point users to React frontend; keep Flask read-only for rollback window
7. **Decommission Flask** — After validation period, retire `modern-EMR-main` on port 5000

## API Mapping (Flask → FastAPI)

| Flask | FastAPI |
|-------|---------|
| `POST /login` | `POST /api/v1/auth/login` |
| `GET /patients` | `GET /api/v1/patients?q=` |
| `POST /patient/add` | `POST /api/v1/patients` |
| `POST /patient/<id>/visit/add` | `POST /api/v1/patients/{id}/visits` |
| `GET /visit/<id>` | `GET /api/v1/visits/{id}` |
| `POST /api/add_prescription` | `POST /api/v1/visits/{id}/prescriptions` |
| `GET /api/search_generic` | `GET /api/v1/medications/search?q=` |
| `GET /visit/<id>/prescription/pdf` | `GET /api/v1/visits/{id}/prescription/pdf` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://emr:emr_secret@localhost:5432/endo_emr` | PostgreSQL connection |
| `JWT_SECRET` | (change in production) | JWT signing key |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins |
| `SEED_ON_STARTUP` | `false` | Seed demo data if DB empty |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base URL |

## Rollback

If issues arise after cutover:

1. Point users back to Flask on port 5000
2. Flask SQLite DB was kept read-only during testing — no data loss from new stack if migration was one-way after validation
3. Fix issues in FastAPI stack and re-migrate if needed
