"""Registration gate, purchase numbering and deactivated accounts."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_hardening.db")
os.environ.setdefault("SEED_ON_STARTUP", "true")

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.services.invoice_series import next_document_number
from app.services.seed_data import seed_if_empty
from app.services.seed_staff import seed_staff_users


def _setup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        seed_staff_users(db)
    finally:
        db.close()


def _login(client, email="demo@clinic.com", password="password123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


NEW_DOCTOR = {
    "email": "new.doctor@example.com",
    "password": "a-long-password-1",
    "display_name": "Dr New",
}


def test_anonymous_cannot_create_a_doctor_account():
    _setup()
    with TestClient(app) as client:
        r = client.post("/api/v1/auth/register", json=NEW_DOCTOR)
        assert r.status_code == 403, r.text


def test_signed_in_doctor_can_add_a_doctor_but_a_desk_user_cannot():
    _setup()
    with TestClient(app) as client:
        desk = _login(client, "billing@clinic.com")
        r = client.post("/api/v1/auth/register", json=NEW_DOCTOR, headers={"Authorization": f"Bearer {desk}"})
        assert r.status_code == 403, r.text
        doctor = _login(client)
        r = client.post(
            "/api/v1/auth/register",
            json={**NEW_DOCTOR, "email": "second.doctor@example.com"},
            headers={"Authorization": f"Bearer {doctor}"},
        )
        assert r.status_code == 201, r.text


def test_purchase_invoice_numbers_are_issued():
    _setup()
    db = SessionLocal()
    try:
        number = next_document_number(db, 1, "PUR")
        assert number.startswith("PUR-") and number[-5:].isdigit()
    finally:
        db.close()


def test_deactivated_user_is_locked_out_at_once():
    _setup()
    with TestClient(app) as client:
        token = _login(client, "pharmacy@clinic.com")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "pharmacy@clinic.com").first()
            user.is_active = False
            db.commit()
        finally:
            db.close()
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (401, 403), r.text
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "pharmacy@clinic.com").first()
            user.is_active = True
            db.commit()
        finally:
            db.close()
