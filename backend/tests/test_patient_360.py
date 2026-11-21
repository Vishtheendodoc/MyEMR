"""Patient 360 aggregation and doctor-only access."""

import os
from datetime import date, datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_emr.db")
os.environ.setdefault("SEED_ON_STARTUP", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Visit
from app.services.db_migrate import ensure_phase2_columns
from app.services.patient_360 import canonical_code, diff_medications
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


def test_canonical_lab_names_do_not_collapse_distinct_tests():
    assert canonical_code("HbA1c") == "hba1c"
    assert canonical_code("HbA1c %") == "hba1c"
    assert canonical_code("FT4") == "ft4"
    assert canonical_code("Free T4") == "ft4"
    assert canonical_code("Total T4") is None
    assert canonical_code("Serum creatinine") == "creatinine"
    assert canonical_code("HDL cholesterol") == "hdl"
    assert canonical_code("Total cholesterol") == "total_cholesterol"


def test_medication_diff_matches_on_generic_name():
    previous = [{
        "identity": "metformin",
        "drug_name": "Glyciphage",
        "generic_name": "Metformin",
        "signature": "500 mg · 1-0-1",
    }]
    current = [{
        "identity": "metformin",
        "drug_name": "Glycomet",
        "generic_name": "Metformin",
        "signature": "1000 mg · 1-0-1",
    }, {
        "identity": "vitamin d",
        "drug_name": "Vitamin D",
        "generic_name": None,
        "signature": "60000 IU · once weekly",
    }]
    changes = diff_medications(previous, current)
    kinds = {(row["change"], row["generic_name"] or row["drug_name"]) for row in changes}
    assert ("changed", "Metformin") in kinds
    assert ("added", "Vitamin D") in kinds
    assert not any(row["change"] == "stopped" for row in changes)


def test_patient_360_snapshot_and_role_gate():
    doctor = _login("demo@clinic.com")
    registration = _login("registration@clinic.com")
    billing = _login("billing@clinic.com")
    pharmacy = _login("pharmacy@clinic.com")

    created = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Patient Three Sixty",
        "age": "55",
        "sex": "Male",
        "contact": "9876501234",
        "allergies": "Penicillin",
        "problem_list": "Type 2 diabetes mellitus",
    })
    assert created.status_code == 201, created.text
    patient_id = created.json()["id"]

    def make_visit(weight: float, systolic: int, diastolic: int) -> int:
        response = client.post(f"/api/v1/patients/{patient_id}/visits", headers=doctor, json={
            "visit_type": "Review",
            "diagnosis": "Type 2 Diabetes Mellitus",
            "height": 170,
            "weight": weight,
            "bp_systolic": systolic,
            "bp_diastolic": diastolic,
            "comorbidities": "CKD",
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    older_id = make_visit(80, 140, 90)
    newer_id = make_visit(76, 128, 82)

    def prescribe(visit_id: int, dosage: str):
        response = client.post(f"/api/v1/visits/{visit_id}/prescriptions", headers=doctor, json={
            "custom_drug_name": "Metformin",
            "custom_generic_name": "Metformin",
            "dosage": dosage,
            "frequency": "1-0-1",
            "duration": "30 days",
        })
        assert response.status_code == 201, response.text

    prescribe(older_id, "500 mg")
    prescribe(newer_id, "1000 mg")

    for value, result_date in (("8.5", "2025-01-10"), ("7.4", "2026-06-01")):
        response = client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
            "test_name": "HbA1c",
            "value": value,
            "unit": "%",
            "result_date": result_date,
        })
        assert response.status_code == 201, response.text

    renal = client.post(f"/api/v1/patients/{patient_id}/labs", headers=doctor, json={
        "test_name": "Creatinine",
        "value": "1.4",
        "unit": "mg/dL",
        "result_date": "2026-06-01",
    })
    assert renal.status_code == 201, renal.text

    session = SessionLocal()
    try:
        older = session.get(Visit, older_id)
        newer = session.get(Visit, newer_id)
        assert older and newer
        older.visit_date = datetime(2025, 1, 15, 4, 30)
        newer.visit_date = datetime(2026, 6, 2, 4, 30)
        newer.follow_up_date = date(2026, 6, 20)
        session.commit()
    finally:
        session.close()

    denied = client.get(f"/api/v1/patients/{patient_id}/patient-360")
    assert denied.status_code == 401

    for headers in (registration, billing, pharmacy):
        blocked = client.get(f"/api/v1/patients/{patient_id}/patient-360", headers=headers)
        assert blocked.status_code == 403, blocked.text
        still_open = client.get(f"/api/v1/patients/{patient_id}", headers=headers)
        assert still_open.status_code == 200

    missing = client.get("/api/v1/patients/99999999/patient-360", headers=doctor)
    assert missing.status_code == 404

    response = client.get(f"/api/v1/patients/{patient_id}/patient-360", headers=doctor)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["overview"]["allergies"] == "Penicillin"
    assert body["overview"]["current_medications_visit_id"] == newer_id
    assert body["overview"]["current_medications"][0]["generic_name"] == "Metformin"
    assert any(item["text"] == "Type 2 Diabetes Mellitus" for item in body["overview"]["active_diagnoses"])

    by_code = {row["code"]: row for row in body["parameters"]}
    assert by_code["hba1c"]["latest"]["value_text"] == "7.4"
    assert by_code["hba1c"]["previous"]["value_text"] == "8.5"
    assert by_code["weight"]["latest"]["value_text"] == "76"
    assert by_code["egfr"]["latest"]["source"] == "calculated"
    assert by_code["egfr"]["latest"]["value_numeric"] < 60
    assert by_code["uacr"]["latest"] is None

    prompt_codes = {item["code"] for item in body["overview"]["prompts"]}
    assert "allergy" in prompt_codes
    assert "egfr_low" in prompt_codes
    assert "follow_up_overdue" in prompt_codes
    assert "screening_uacr" in prompt_codes
    assert "hba1c_high" not in prompt_codes
    assert "screening_hba1c" not in prompt_codes

    comparison = body["comparison"]
    assert comparison["available"] is True
    assert comparison["current_visit_id"] == newer_id
    assert comparison["previous_visit_id"] == older_id
    assert any(row["change"] == "changed" and row["generic_name"] == "Metformin" for row in comparison["medication_changes"])
    assert any(row["code"] == "hba1c" and row["direction"] == "lower" for row in comparison["parameter_changes"])
    assert any(row["code"] == "weight" and row["direction"] == "lower" for row in comparison["vital_changes"])

    kinds = {event["kind"] for event in body["timeline"]}
    assert {"registration", "consultation", "prescription", "laboratory", "follow_up"} <= kinds
    hba1c_chart = next(group for group in body["trends"] if group["id"] == "hba1c")
    assert [point["value"] for point in hba1c_chart["series"][0]["points"]] == [8.5, 7.4]

    detail = client.get(f"/api/v1/patients/{patient_id}", headers=doctor)
    assert detail.status_code == 200
    assert "parameters" not in detail.json()

    imaging = {
        "study_type": "USG Pelvis",
        "findings": "Same report",
        "report_date": "2026-06-01",
    }
    assert client.post(f"/api/v1/patients/{patient_id}/imaging", headers=doctor, json=imaging).status_code == 201
    assert client.post(f"/api/v1/patients/{patient_id}/imaging", headers=doctor, json=imaging).status_code == 201
    again = client.get(f"/api/v1/patients/{patient_id}/patient-360", headers=doctor)
    assert again.status_code == 200, again.text
    imaging_events = [
        event for event in again.json()["timeline"]
        if event["kind"] == "imaging" and event["detail"] == "Same report"
    ]
    assert len(imaging_events) == 1
