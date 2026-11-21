"""Clinical observation sync, migration, and doctor-only access."""

import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_emr.db")
os.environ.setdefault("SEED_ON_STARTUP", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import ClinicalObservation, LabResult
from app.services.db_migrate import ensure_phase2_columns
from app.services.observation_sync import (
    backfill_all,
    parse_reference_bounds,
    sync_patient_observations,
)
from app.services.seed_data import seed_if_empty
from app.services.seed_extensions import seed_extensions_if_missing
from app.services.seed_staff import seed_staff_users

Base.metadata.create_all(bind=engine)
ensure_phase2_columns()
db = SessionLocal()
try:
    seed_if_empty(db)
    seed_extensions_if_missing(db)
    seed_staff_users(db)
finally:
    db.close()

client = TestClient(app)


def _login(email: str, password: str = "password123") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_reference_bounds_keep_unparsed_text_without_numbers():
    assert parse_reference_bounds("70-100") == (70.0, 100.0)
    assert parse_reference_bounds("0.4–4.5") == (0.4, 4.5)
    assert parse_reference_bounds("<7.0") == (None, 7.0)
    assert parse_reference_bounds(">40") == (40.0, None)
    assert parse_reference_bounds("age-adjusted") == (None, None)


def test_backfill_does_not_duplicate_an_existing_lab():
    session = SessionLocal()
    try:
        lab = LabResult(
            patient_id=1,
            test_name="HbA1c",
            value="8.1",
            unit="%",
            reference_range="<7.0",
            result_date=date(2026, 1, 2),
        )
        session.add(lab)
        session.commit()
        lab_id = lab.id
        first = sync_patient_observations(session, 1)
        session.commit()
        second = sync_patient_observations(session, 1)
        session.commit()
        rows = (
            session.query(ClinicalObservation)
            .filter_by(source_record_type="lab_result", source_record_id=lab_id)
            .all()
        )
        assert first >= 1
        assert second >= 1
        assert len(rows) == 1
        assert rows[0].observation_code == "hba1c"
        assert rows[0].value_text == "8.1"
        assert rows[0].unit == "%"
        assert rows[0].reference_range == "<7.0"
        assert rows[0].reference_range_high == 7.0
        assert rows[0].source == "laboratory"
        session.delete(lab)
        session.query(ClinicalObservation).filter_by(source_record_id=lab_id, source_record_type="lab_result").delete()
        session.commit()
    finally:
        session.close()


def test_observation_api_roles_and_sources():
    doctor = _login("demo@clinic.com")
    registration = _login("registration@clinic.com")
    billing = _login("billing@clinic.com")
    pharmacy = _login("pharmacy@clinic.com")

    created = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Observation Patient",
        "age": "44",
        "sex": "Female",
        "contact": "9876501111",
    })
    assert created.status_code == 201, created.text
    patient_id = created.json()["id"]

    visit = client.post(f"/api/v1/patients/{patient_id}/visits", headers=doctor, json={
        "visit_type": "Review",
        "height": 160,
        "weight": 64,
        "bp_systolic": 120,
        "bp_diastolic": 80,
    })
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["id"]

    lab = client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
        "test_name": "TSH",
        "value": "2.5",
        "unit": "mIU/L",
        "reference_range": "0.4-4.5",
        "result_date": "2026-03-01",
        "visit_id": visit_id,
    })
    assert lab.status_code == 201, lab.text
    lab_id = lab.json()["id"]
    assert "observation_code" not in lab.json()

    denied = client.get(f"/api/v1/patients/{patient_id}/observations")
    assert denied.status_code == 401
    for headers in (registration, billing, pharmacy):
        blocked = client.get(f"/api/v1/patients/{patient_id}/observations", headers=headers)
        assert blocked.status_code == 403, blocked.text
        assert client.get(f"/api/v1/patients/{patient_id}", headers=headers).status_code == 200

    listed = client.get(f"/api/v1/patients/{patient_id}/observations", headers=doctor)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    tsh = [row for row in body if row["source_record_type"] == "lab_result" and row["source_record_id"] == lab_id]
    assert len(tsh) == 1
    assert tsh[0]["observation_code"] == "tsh"
    assert tsh[0]["reference_range_low"] == 0.4
    assert tsh[0]["reference_range_high"] == 4.5
    weights = [row for row in body if row["observation_code"] == "weight" and row["source_record_id"] == visit_id]
    assert len(weights) == 1
    assert weights[0]["source"] == "examination"
    assert weights[0]["value_text"] == "64"

    again = client.get(f"/api/v1/patients/{patient_id}/observations", headers=doctor)
    assert len([row for row in again.json() if row["source_record_id"] == lab_id]) == 1

    extracted = client.post(f"/api/v1/patients/{patient_id}/observations", headers=doctor, json={
        "observation_code": "ft4",
        "observation_name": "FT4",
        "value_text": "1.2",
        "unit": "ng/dL",
        "observed_at": "2026-03-01",
        "source": "laboratory_report",
    })
    assert extracted.status_code == 201, extracted.text
    assert extracted.json()["verification_status"] == "pending"
    assert extracted.json()["verified_by"] is None
    assert extracted.json()["source_record_id"] is None

    blocked_verify = client.post(f"/api/v1/observations/{extracted.json()['id']}/verify", headers=registration)
    assert blocked_verify.status_code == 403
    verified = client.post(f"/api/v1/observations/{extracted.json()['id']}/verify", headers=doctor)
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification_status"] == "verified"
    assert verified.json()["verified_by"] is not None

    removed = client.delete(f"/api/v1/labs/{lab_id}", headers=doctor)
    assert removed.status_code == 204
    after = client.get(f"/api/v1/patients/{patient_id}/observations", headers=doctor)
    assert all(row["source_record_id"] != lab_id for row in after.json())


def test_alembic_upgrade_backfills_without_duplicating():
    backend = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "migrate.db"
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
        env["SEED_ON_STARTUP"] = "false"

        def alembic(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, "-m", "alembic", *args],
                cwd=backend,
                env=env,
                capture_output=True,
                text=True,
            )

        base = alembic("upgrade", "002")
        assert base.returncode == 0, base.stderr[-2000:]

        from sqlalchemy import create_engine, text

        migrate_engine = create_engine(env["DATABASE_URL"])
        with migrate_engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO lab_result (patient_id, test_name, value, unit, reference_range, result_date, created_at) "
                "VALUES (1, 'Creatinine', '1.1', 'mg/dL', '0.6-1.2', '2026-02-02', '2026-02-02 00:00:00')"
            ))

        upgraded = alembic("upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr[-2000:]

        from app.services.observation_sync import backfill_connection

        with migrate_engine.begin() as connection:
            backfill_connection(connection)
            count = connection.execute(text(
                "SELECT COUNT(*) FROM clinical_observation WHERE observation_code = 'creatinine'"
            )).scalar()
            sample = connection.execute(text(
                "SELECT value_text, unit, source_record_type FROM clinical_observation WHERE observation_code = 'creatinine'"
            )).one()
        assert count == 1
        assert sample[0] == "1.1"
        assert sample[1] == "mg/dL"
        assert sample[2] == "lab_result"
        migrate_engine.dispose()
