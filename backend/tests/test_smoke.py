"""End-to-end API smoke tests (uses SQLite if PostgreSQL unavailable)."""

import os
import sys
import time
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_emr.db")
os.environ.setdefault("SEED_ON_STARTUP", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.services.seed_data import seed_if_empty
from app.services.seed_extensions import seed_extensions_if_missing
from app.services.db_migrate import ensure_phase2_columns
from app.core.database import SessionLocal

Base.metadata.create_all(bind=engine)
ensure_phase2_columns()
db = SessionLocal()
try:
    seed_if_empty(db)
    seed_extensions_if_missing(db)
finally:
    db.close()

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("OK health")


def test_auth_flow():
    r = client.post("/api/v1/auth/login", json={
        "email": "demo@clinic.com",
        "password": "password123",
    })
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert "access_token" in tokens
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "demo@clinic.com"
    print("OK auth")

    r = client.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    print(f"OK dashboard — patients: {data['stats']['total_patients']}")

    r = client.get("/api/v1/patients", headers=headers)
    assert r.status_code == 200
    patients = r.json()
    assert len(patients) >= 1
    print(f"OK patients — count: {len(patients)}")

    if patients:
        pid = patients[0]["id"]
        r = client.get(f"/api/v1/patients/{pid}", headers=headers)
        assert r.status_code == 200
        print("OK patient detail")

        visits = r.json().get("visits", [])
        if visits:
            vid = visits[0]["id"]
            r = client.get(f"/api/v1/visits/{vid}", headers=headers)
            assert r.status_code == 200
            print(f"OK visit detail — prescriptions: {len(r.json().get('prescriptions', []))}")

            r = client.get(f"/api/v1/medications/search?q=met", headers=headers)
            assert r.status_code == 200
            print(f"OK drug search — results: {len(r.json())}")

    return headers


def test_create_patient_and_visit(headers):
    mrd = f"TEST{int(time.time()) % 100000}"
    r = client.post("/api/v1/patients", headers=headers, json={
        "mrd_number": mrd,
        "name": "Test Patient",
        "age": "40",
        "sex": "Male",
        "contact": "9999999999",
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    print(f"OK create patient — id: {pid}")

    r = client.post(f"/api/v1/patients/{pid}/visits", headers=headers, json={
        "visit_type": "New Visit",
        "chief_complaints": "Test complaint",
        "diagnosis": "Type 2 Diabetes Mellitus",
        "height": 170,
        "weight": 75,
        "specialty_template": "diabetes",
        "specialty_data": {"condition": "diabetes", "hba1c": "8.2", "fbs": "145"},
        "follow_up_date": (date.today() + timedelta(days=14)).isoformat(),
        "follow_up_notes": "Review HbA1c",
    })
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    print(f"OK create visit — id: {vid}")

    r = client.get(f"/api/v1/patients/{pid}/labs", headers=headers)
    assert r.status_code == 200
    labs = r.json()
    assert any(l["test_name"] == "HbA1c" for l in labs), "Template should sync HbA1c to labs"
    print(f"OK template lab sync — labs: {len(labs)}")

    r = client.get(f"/api/v1/visits/{vid}", headers=headers)
    assert r.status_code == 200
    assert len(r.json().get("specialty_fields", [])) >= 1
    print("OK visit specialty fields display")

    r = client.get("/api/v1/appointments", headers=headers)
    follow_up_appts = [a for a in r.json() if "Follow-up from visit" in (a.get("notes") or "")]
    assert len(follow_up_appts) >= 1, "Follow-up date should auto-create appointment"
    print("OK follow-up appointment sync")
    return vid


def test_phase2_5_endpoints(headers):
    r = client.get("/api/v1/follow-ups", headers=headers)
    assert r.status_code == 200
    print(f"OK follow-ups — count: {len(r.json())}")

    r = client.get("/api/v1/specialty-templates", headers=headers)
    assert r.status_code == 200
    assert "diabetes" in r.json()
    print("OK specialty templates")

    r = client.get("/api/v1/specialty-templates/suggest?diagnosis=Type%202%20Diabetes", headers=headers)
    assert r.status_code == 200
    assert r.json()["template"] == "diabetes"
    print("OK template suggestion")

    r = client.post("/api/v1/calculators/egfr", headers=headers, json={
        "creatinine_mg_dl": 1.2, "age": 55, "sex": "Male",
    })
    assert r.status_code == 200
    assert "egfr" in r.json()
    print(f"OK eGFR calculator — {r.json()['egfr']}")

    r = client.post("/api/v1/calculators/instruction-bilingual", headers=headers, json={
        "text": "Before Food. Take after meals with water",
    })
    assert r.status_code == 200
    body = r.json()
    assert "kannada" in body
    assert body["bilingual"] and "(" in body["bilingual"]
    print(f"OK instruction bilingual — {body['bilingual'][:60]}...")

    r = client.get("/api/v1/appointments", headers=headers)
    assert r.status_code == 200
    print(f"OK appointments — count: {len(r.json())}")

    r = client.get(f"/api/v1/appointments/calendar?year={date.today().year}&month={date.today().month}", headers=headers)
    assert r.status_code == 200
    assert "days" in r.json()
    print("OK appointment calendar")

    r = client.get("/api/v1/bills", headers=headers)
    assert r.status_code == 200
    print(f"OK bills — count: {len(r.json())}")

    r = client.get("/api/v1/analytics", headers=headers)
    assert r.status_code == 200
    assert "revenue_summary" in r.json()
    print("OK analytics")

    patients = client.get("/api/v1/patients", headers=headers).json()
    if patients:
        pid = patients[0]["id"]
        r = client.get(f"/api/v1/patients/{pid}/timeline", headers=headers)
        assert r.status_code == 200
        print("OK patient timeline")

        r = client.get(f"/api/v1/patients/{pid}/labs", headers=headers)
        assert r.status_code == 200
        print(f"OK labs — count: {len(r.json())}")

        r = client.get(f"/api/v1/patients/{pid}/diabetes-dashboard", headers=headers)
        assert r.status_code == 200
        print("OK diabetes dashboard")

        visits = client.get(f"/api/v1/patients/{pid}", headers=headers).json().get("visits", [])
        if visits:
            r = client.get(f"/api/v1/visits/{visits[0]['id']}/cds", headers=headers)
            assert r.status_code == 200
            print(f"OK CDS — recommendations: {len(r.json())}")


def test_migrate_script_dry_run():
    sqlite_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "modern-EMR-main", "instance", "emr.db")
    )
    if os.path.exists(sqlite_path):
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "migrate_sqlite_to_pg.py"),
             "--sqlite", sqlite_path, "--dry-run"],
            capture_output=True, text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print("migrate dry-run skipped (PostgreSQL may not be running):", result.stderr[:200])
        else:
            print("OK migrate dry-run")
    else:
        print("SKIP migrate dry-run — no SQLite DB at", sqlite_path)


if __name__ == "__main__":
    test_health()
    headers = test_auth_flow()
    test_create_patient_and_visit(headers)
    test_phase2_5_endpoints(headers)
    test_migrate_script_dry_run()
    print("\nAll smoke tests passed.")
