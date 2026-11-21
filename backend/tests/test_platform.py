"""Modules 3–10: alerts, CGM metrics, medication safety, analytics, sessions."""

import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_emr.db")
os.environ.setdefault("SEED_ON_STARTUP", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import CgmReading
from app.services.cgm_metrics import cgm_summary
from app.services.db_migrate import ensure_phase2_columns
from app.services.platform_seed import seed_platform
from app.services.sqlite_backup import backup_sqlite, restore_sqlite

Base.metadata.create_all(bind=engine)
ensure_phase2_columns()
db = SessionLocal()
try:
    seed_platform(db)
finally:
    db.close()

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["refresh_token"]


def _patient(headers, name: str) -> int:
    response = client.post("/api/v1/patients", headers=headers, json={
        "name": name,
        "age": "54",
        "sex": "Female",
        "contact": "9000000000",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_hba1c_alert_is_one_row_and_desk_cannot_open_it():
    doctor, _ = _login("demo@clinic.com")
    registration, _ = _login("registration@clinic.com")
    patient_id = _patient(doctor, "Alert Patient")
    lab = client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
        "test_name": "HbA1c",
        "value": "9.4",
        "unit": "%",
        "result_date": "2026-03-01",
    })
    assert lab.status_code == 201, lab.text
    first = client.get(f"/api/v1/patients/{patient_id}/intelligence", headers=doctor)
    second = client.get(f"/api/v1/patients/{patient_id}/intelligence", headers=doctor)
    assert first.status_code == 200, first.text
    codes = [row["rule_code"] for row in first.json()["alerts"]]
    assert codes.count("hba1c_review") == 1
    assert "the diagnosis is" not in first.json()["alerts"][0]["explanation"].lower()
    assert [row["rule_code"] for row in second.json()["alerts"]].count("hba1c_review") == 1
    blocked = client.get(f"/api/v1/patients/{patient_id}/intelligence", headers=registration)
    assert blocked.status_code == 403
    mild = client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
        "test_name": "HbA1c",
        "value": "7.2",
        "unit": "%",
        "result_date": "2026-04-01",
    })
    assert mild.status_code == 201
    # A later 7.2 does not by itself keep the 9.4 review, because the latest value is used.
    refreshed = client.get(f"/api/v1/patients/{patient_id}/intelligence", headers=doctor)
    assert "hba1c_review" not in [row["rule_code"] for row in refreshed.json()["alerts"]]


def test_single_moderate_hba1c_does_not_open_the_high_review():
    doctor, _ = _login("demo@clinic.com")
    patient_id = _patient(doctor, "Moderate HbA1c")
    client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
        "test_name": "HbA1c",
        "value": "7.4",
        "unit": "%",
        "result_date": "2026-04-02",
    })
    response = client.get(f"/api/v1/patients/{patient_id}/intelligence", headers=doctor)
    assert "hba1c_review" not in [row["rule_code"] for row in response.json()["alerts"]]


def test_dismiss_requires_a_reason():
    doctor, _ = _login("demo@clinic.com")
    patient_id = _patient(doctor, "Dismiss Patient")
    client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
        "test_name": "TSH",
        "value": "12",
        "unit": "mIU/L",
        "result_date": "2026-04-03",
    })
    listed = client.get(f"/api/v1/patients/{patient_id}/intelligence", headers=doctor)
    alert_id = next(row["id"] for row in listed.json()["alerts"] if row["rule_code"] == "tsh_review")
    missing = client.post(f"/api/v1/alerts/{alert_id}/dismiss", headers=doctor, json={"reason": "no"})
    assert missing.status_code == 422
    done = client.post(f"/api/v1/alerts/{alert_id}/dismiss", headers=doctor, json={"reason": "Reviewed with the patient"})
    assert done.status_code == 200
    assert done.json()["status"] == "dismissed"


def test_cgm_time_in_range_uses_standard_bounds():
    readings = []
    for value in [80, 90, 100, 110, 120, 130, 140, 150, 60, 200]:
        readings.append(type("Row", (), {"glucose_mg_dl": value})())
    summary = cgm_summary(readings)
    assert summary["time_in_range"] == 80.0
    assert summary["time_below_range"] == 10.0
    assert summary["time_above_range"] == 10.0
    assert summary["gmi"] == round(3.31 + 0.02392 * (sum(row.glucose_mg_dl for row in readings) / 10), 2)


def test_medication_checks_do_not_change_the_prescription():
    doctor, _ = _login("demo@clinic.com")
    patient_id = _patient(doctor, "Safety Patient")
    client.patch(f"/api/v1/patients/{patient_id}", headers=doctor, json={"allergies": "penicillin"})
    visit = client.post(f"/api/v1/patients/{patient_id}/visits", headers=doctor, json={
        "visit_type": "Review",
        "diagnosis": "Type 2 diabetes",
    })
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["id"]
    first = client.post(f"/api/v1/visits/{visit_id}/prescriptions", headers=doctor, json={
        "custom_drug_name": "Glycomet",
        "custom_generic_name": "metformin",
        "dosage": "500 mg",
        "frequency": "BD",
        "duration": "30 days",
    })
    second = client.post(f"/api/v1/visits/{visit_id}/prescriptions", headers=doctor, json={
        "custom_drug_name": "Penicillin VK",
        "custom_generic_name": "penicillin",
        "dosage": "500 mg",
        "frequency": "TDS",
        "duration": "5 days",
    })
    third = client.post(f"/api/v1/visits/{visit_id}/prescriptions", headers=doctor, json={
        "custom_drug_name": "Calcium carbonate",
        "custom_generic_name": "calcium",
        "dosage": "500 mg",
        "frequency": "OD",
        "duration": "30 days",
    })
    fourth = client.post(f"/api/v1/visits/{visit_id}/prescriptions", headers=doctor, json={
        "custom_drug_name": "Thyronorm",
        "custom_generic_name": "levothyroxine",
        "dosage": "50 mcg",
        "frequency": "OD",
        "duration": "30 days",
    })
    assert first.status_code == 201 and second.status_code == 201
    session = SessionLocal()
    try:
        from app.models import ClinicalObservation

        session.add(ClinicalObservation(
            patient_id=patient_id,
            observation_code="egfr",
            observation_name="eGFR",
            value_numeric=30,
            value_text="30",
            unit="mL/min/1.73m²",
            observed_at=datetime.utcnow(),
            source="manual",
            verification_status="verified",
        ))
        session.commit()
    finally:
        session.close()
    report = client.get(f"/api/v1/patients/{patient_id}/medication-safety", headers=doctor)
    assert report.status_code == 200, report.text
    body = report.json()
    assert any(row["molecule"] == "metformin" for row in body["duplicates"]) is False
    assert any(row["medicine"] == "Penicillin VK" for row in body["allergy_warnings"])
    assert any("levothyroxine" in row["drugs"] and "calcium" in row["drugs"] for row in body["drug_interactions"])
    assert any(row["medicine"] == "Glycomet" for row in body["renal_review"])
    prescription_id = first.json()["prescription_id"]
    brand_before = client.post(f"/api/v1/patients/{patient_id}/substitutions", headers=doctor, json={
        "prescription_id": prescription_id,
        "requested_brand": "Other brand",
        "reason": "Stock",
    })
    assert brand_before.status_code == 201
    approved = client.post(f"/api/v1/substitutions/{brand_before.json()['id']}/approve", headers=doctor)
    assert approved.json()["unchanged"] is True
    assert approved.json()["brand_medication_id"] == brand_before.json()["brand_medication_id"]
    blocked = client.get(f"/api/v1/patients/{patient_id}/medication-safety", headers=_login("pharmacy@clinic.com")[0])
    assert blocked.status_code == 403
    assert third.status_code == 201 and fourth.status_code == 201


def test_revenue_buckets_stay_separate():
    doctor, _ = _login("demo@clinic.com")
    patient_id = _patient(doctor, "Revenue Patient")
    visit = client.post(f"/api/v1/patients/{patient_id}/visits", headers=doctor, json={"visit_type": "New Visit"})
    visit_id = visit.json()["id"]
    before = client.get("/api/v1/analytics", headers=doctor).json()["practice"]["business"]
    for amount, category, description in ((80, "visit", "Consult"), (40, "pharmacy", "Pharmacy sale"), (25, "lab", "Lab panel")):
        visit = client.post(f"/api/v1/patients/{patient_id}/visits", headers=doctor, json={"visit_type": "New Visit"})
        assert visit.status_code == 201, visit.text
        billed = client.post("/api/v1/bills", headers=doctor, json={
            "visit_id": visit.json()["id"],
            "description": description,
            "category": category,
            "base_amount": amount,
            "gst_percent": 0,
            "gst_amount": 0,
            "amount": amount,
            "payment_status": "paid",
        })
        assert billed.status_code == 201, billed.text
    after = client.get("/api/v1/analytics", headers=doctor).json()["practice"]["business"]
    assert round(after["consultation_revenue"] - before["consultation_revenue"], 2) == 80
    assert round(after["pharmacy_turnover"] - before["pharmacy_turnover"], 2) == 40
    assert round(after["laboratory_revenue"] - before["laboratory_revenue"], 2) == 25
    assert after["pharmacy_gross_margin"] is None
    blocked = client.get("/api/v1/analytics", headers=_login("billing@clinic.com")[0])
    assert blocked.status_code == 403


def test_refresh_token_cannot_be_reused_and_labs_are_doctor_only():
    doctor, refresh = _login("demo@clinic.com")
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200, rotated.text
    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401
    client.post("/api/v1/auth/logout", json={"refresh_token": rotated.json()["refresh_token"]})
    after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]})
    assert after_logout.status_code == 401
    registration, _ = _login("registration@clinic.com")
    patient_id = _patient(doctor, "Role Patient")
    labs = client.get(f"/api/v1/patients/{patient_id}/labs", headers=registration)
    assert labs.status_code == 403
    chart = client.get(f"/api/v1/patients/{patient_id}", headers=registration)
    assert chart.status_code == 200
    assert all(visit["diagnosis"] is None for visit in chart.json()["visits"])
    fhir = client.get(f"/api/v1/fhir/Patient/{patient_id}", headers=registration)
    assert fhir.status_code == 403
    own = client.get(f"/api/v1/fhir/Patient/{patient_id}", headers=doctor)
    assert own.json()["resourceType"] == "Patient"
    assert "Not a certified" in own.json()["meta"]["tag"][0]["display"]
    status = client.get("/api/v1/interop/status", headers=doctor)
    assert status.json()["abdm_abha"]["configured"] is False
    assert status.json()["fhir_r4"]["certified"] is False


def test_sqlite_backup_round_trip():
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "clinic.db"
        copy = Path(folder) / "backup.db"
        restored = Path(folder) / "restored.db"
        connection = sqlite3.connect(source)
        connection.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, label TEXT)")
        connection.execute("INSERT INTO marker (label) VALUES ('kept')")
        connection.commit()
        connection.close()
        backup_sqlite(source, copy)
        restore_sqlite(copy, restored)
        check = sqlite3.connect(restored)
        assert check.execute("SELECT label FROM marker").fetchone()[0] == "kept"
        check.close()


def test_alembic_creates_versioned_rules():
    backend = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "migrate.db"
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
        env["SEED_ON_STARTUP"] = "false"
        upgraded = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
        )
        assert upgraded.returncode == 0, upgraded.stderr[-2000:]
        connection = sqlite3.connect(database)
        count = connection.execute("SELECT COUNT(*) FROM clinical_rule").fetchone()[0]
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        connection.close()
        assert count >= 10
        assert "patient_care_plan" not in names
        assert "monitoring_schedule" not in names
        assert "research_ethics" not in names
        assert "research_consent" not in names
        assert "research_subject" not in names
        again = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
        )
        assert again.returncode == 0, again.stderr[-2000:]


def test_cgm_endpoint_reports_a_low_night_reading():
    doctor, _ = _login("demo@clinic.com")
    patient_id = _patient(doctor, "CGM Patient")
    session = SessionLocal()
    try:
        session.add(CgmReading(
            patient_id=patient_id,
            glucose_mg_dl=55,
            reading_time=datetime.utcnow().replace(hour=0, minute=30, second=0, microsecond=0),
            source="manual",
        ))
        session.commit()
    finally:
        session.close()
    response = client.get(f"/api/v1/patients/{patient_id}/diabetes-dashboard?days=14", headers=doctor)
    assert response.status_code == 200, response.text
    assert response.json()["cgm_metrics"]["reading_count"] == 1
    assert response.json()["cgm_metrics"]["time_below_range"] == 100.0
    assert "Meal times are not stored" in response.json()["postprandial"]["note"]


if __name__ == "__main__":
    import traceback

    failed = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"OK {name}")
            except Exception:
                failed += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    if failed:
        raise SystemExit(f"{failed} failed")
    print("All platform tests passed")
