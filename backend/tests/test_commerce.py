"""Purchases, expiry blocks, returns, and finance totals."""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_commerce.db"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["JWT_SECRET"] = "test-secret-key"

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.clinic_admin import consume_stock
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Bill, BillPayment, InventoryTxn, StockBatch
from app.services.db_migrate import ensure_phase2_columns

Base.metadata.create_all(bind=engine)
ensure_phase2_columns()
client = TestClient(app)
client.__enter__()


def _login() -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "demo@clinic.com", "password": "password123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_purchase_posts_stock_and_refuses_a_duplicate_invoice():
    doctor = _login()
    supplier = client.post("/api/v1/commerce/suppliers", headers=doctor, json={"name": "Shree Pharma", "gstin": "29ABCDE1234F1Z5"})
    assert supplier.status_code == 201, supplier.text
    body = {
        "supplier_id": supplier.json()["id"],
        "supplier_invoice_no": "SUP-100",
        "lines": [{
            "medicine_name": "Zyrova 10",
            "batch_no": "B1",
            "expiry_date": "2027-12-31",
            "quantity": 2,
            "unit": "strip",
            "purchase_rate": 50,
            "gst_percent": 12,
            "pack_size": 1,
            "strip_size": 10,
        }],
    }
    first = client.post("/api/v1/commerce/purchases", headers=doctor, json=body)
    assert first.status_code == 201, first.text
    assert first.json()["lines"][0]["base_quantity"] == 20
    second = client.post("/api/v1/commerce/purchases", headers=doctor, json=body)
    assert second.status_code == 400
    db = SessionLocal()
    try:
        batch = db.query(StockBatch).filter_by(item_name="Zyrova 10").one()
        assert batch.quantity == 20
        assert db.query(InventoryTxn).filter_by(txn_type="purchase", medicine_name="Zyrova 10").count() == 1
    finally:
        db.close()


def test_expired_stock_cannot_be_dispensed_and_damaged_returns_stay_in_quarantine():
    doctor = _login()
    db = SessionLocal()
    try:
        db.add(StockBatch(clinic_id=1, item_name="Old Tab", batch_no="OLD", expiry_date=date.today() - timedelta(days=1), quantity=5))
        db.commit()
        try:
            consume_stock(db, 1, "Old Tab", 1)
            raise AssertionError("expired stock was dispensed")
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "Expired" in exc.detail
    finally:
        db.close()

    patient = client.post("/api/v1/patients", headers=doctor, json={"name": "Commerce Patient", "age": "40", "sex": "Female", "contact": "9999900000"})
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    billed = client.post("/api/v1/bills", headers=doctor, json={
        "visit_id": visit.json()["id"],
        "category": "pharmacy",
        "payment_status": "paid",
        "payment_method": "UPI",
        "line_items": [{"description": "Fresh Tab", "procedure_code": "300490", "quantity": 4, "rate": 10, "gst_percent": 12}],
    })
    assert billed.status_code == 201, billed.text
    invoice = billed.json()["invoice_number"]
    assert billed.json()["cgst_amount"] > 0
    assert billed.json()["sgst_amount"] > 0
    returned = client.post("/api/v1/commerce/sales-returns", headers=doctor, json={
        "invoice_number": invoice,
        "description": "Fresh Tab",
        "quantity": 1,
        "reason": "Pack damaged",
        "condition": "damaged",
    })
    assert returned.status_code == 201, returned.text
    db = SessionLocal()
    try:
        quarantine = db.query(StockBatch).filter_by(item_name="Fresh Tab", stock_status="quarantine").one()
        assert quarantine.quantity == 1
        saleable = db.query(StockBatch).filter_by(item_name="Fresh Tab", stock_status="saleable").all()
        assert sum(row.quantity or 0 for row in saleable) == 0
    finally:
        db.close()
    report = client.get("/api/v1/commerce/finance?preset=today", headers=doctor)
    assert report.status_code == 200, report.text
    assert report.json()["pharmacy"] >= billed.json()["amount"]
    assert report.json()["payments"]["upi"] >= billed.json()["amount"]


def test_split_collection_and_cash_drawer():
    doctor = _login()
    patient = client.post("/api/v1/patients", headers=doctor, json={"name": "Split Patient", "age": "33", "sex": "Male", "contact": "9999900001"})
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    billed = client.post("/api/v1/bills", headers=doctor, json={
        "visit_id": visit.json()["id"],
        "category": "visit",
        "line_items": [{"description": "Consultation", "quantity": 1, "rate": 500, "gst_percent": 0}],
        "payments": [{"method": "Cash", "amount": 200}, {"method": "UPI", "amount": 100}],
    })
    assert billed.status_code == 201, billed.text
    body = billed.json()
    assert body["amount_paid"] == 300
    assert body["payment_status"] == "partial"
    assert "Cash" in (body["payment_method"] or "") and "UPI" in (body["payment_method"] or "")
    db = SessionLocal()
    try:
        amounts = sorted(row.amount for row in db.query(BillPayment).filter_by(bill_id=body["id"]).all())
        assert amounts == [100.0, 200.0]
    finally:
        db.close()
    locked = client.post("/api/v1/day-close", headers=doctor, json={"day": "2020-01-02", "opening_cash": 500, "closing_cash": 480})
    assert locked.status_code == 200, locked.text
    assert locked.json()["opening_cash"] == 500
    assert locked.json()["closing_cash"] == 480
    summary = client.get("/api/v1/day-close?day=2020-01-02", headers=doctor)
    assert summary.status_code == 200, summary.text
    assert summary.json()["opening_cash"] == 500
    assert summary.json()["locked"] is True


def test_outstanding_receipt_after_day_close_stays_on_the_new_day():
    doctor = _login()
    patient = client.post("/api/v1/patients", headers=doctor, json={"name": "Later Receipt", "age": "50", "sex": "Male", "contact": "9999900002"})
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    billed = client.post("/api/v1/bills", headers=doctor, json={
        "visit_id": visit.json()["id"],
        "category": "visit",
        "line_items": [{"description": "Consultation", "quantity": 1, "rate": 500, "gst_percent": 0}],
    })
    assert billed.status_code == 201, billed.text
    bill_id = billed.json()["id"]
    db = SessionLocal()
    try:
        row = db.get(Bill, bill_id)
        row.created_at = datetime(2020, 1, 3, 8, 0, 0)
        db.commit()
    finally:
        db.close()
    locked = client.post("/api/v1/day-close", headers=doctor, json={"day": "2020-01-03", "opening_cash": 0, "closing_cash": 0})
    assert locked.status_code == 200, locked.text
    assert locked.json()["collected"] == 0
    paid = client.patch(f"/api/v1/bills/{bill_id}", headers=doctor, json={"amount_paid": 200, "payment_method": "Cash"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["amount_paid"] == 200
    assert paid.json()["payment_status"] == "partial"
    frozen = client.get("/api/v1/day-close?day=2020-01-03", headers=doctor)
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["collected"] == 0
    assert frozen.json()["billed"] == 500
    blocked = client.patch(f"/api/v1/bills/{bill_id}", headers=doctor, json={"payment_status": "cancelled"})
    assert blocked.status_code == 400


def test_only_a_doctor_or_admin_can_reopen_a_locked_day():
    doctor = _login()
    locked = client.post("/api/v1/day-close", headers=doctor, json={"day": "2020-01-04", "opening_cash": 10, "closing_cash": 10})
    assert locked.status_code == 200, locked.text
    desk = client.post("/api/v1/auth/login", json={"email": "billing@clinic.com", "password": "password123"})
    assert desk.status_code == 200, desk.text
    billing = {"Authorization": f"Bearer {desk.json()['access_token']}"}
    denied = client.post("/api/v1/day-close/reopen", headers=billing, json={"day": "2020-01-04"})
    assert denied.status_code == 403, denied.text
    opened = client.post("/api/v1/day-close/reopen", headers=doctor, json={"day": "2020-01-04"})
    assert opened.status_code == 200, opened.text
    assert opened.json()["locked"] is False
    summary = client.get("/api/v1/day-close?day=2020-01-04", headers=doctor)
    assert summary.json()["locked"] is False


def test_today_queue_separates_new_walk_in_and_online_revisit():
    doctor = _login()
    board = client.get("/api/v1/dashboard", headers=doctor)
    assert board.status_code == 200, board.text
    day = board.json()["today"]["date"]
    fresh = client.post("/api/v1/patients", headers=doctor, json={"name": "Queue New", "age": "28", "sex": "Female", "contact": "9999900011"})
    assert fresh.status_code == 201, fresh.text
    walk = client.post("/api/v1/appointments", headers=doctor, json={
        "patient_id": fresh.json()["id"],
        "scheduled_at": f"{day}T09:30:00",
        "channel": "walk_in",
    })
    assert walk.status_code == 201, walk.text
    known = client.post("/api/v1/patients", headers=doctor, json={"name": "Queue Revisit", "age": "46", "sex": "Male", "contact": "9999900012"})
    assert known.status_code == 201, known.text
    visit = client.post(f"/api/v1/patients/{known.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    assert visit.status_code == 201, visit.text
    from app.core.database import SessionLocal
    from app.models import Visit
    from datetime import datetime
    db = SessionLocal()
    try:
        row = db.get(Visit, visit.json()["id"])
        row.visit_date = datetime(2020, 1, 1, 8, 0, 0)
        db.commit()
    finally:
        db.close()
    online = client.post("/api/v1/appointments", headers=doctor, json={
        "patient_id": known.json()["id"],
        "scheduled_at": f"{day}T11:00:00",
        "channel": "online",
    })
    assert online.status_code == 201, online.text
    again = client.get("/api/v1/dashboard", headers=doctor)
    assert again.status_code == 200, again.text
    rows = {item["patient_name"]: item for item in again.json()["today"]["consultations"]}
    assert rows["Queue New"]["kind"] == "new"
    assert rows["Queue New"]["channel"] == "walk_in"
    assert rows["Queue Revisit"]["kind"] == "revisit"
    assert rows["Queue Revisit"]["channel"] == "online"


def test_registration_sends_a_patient_to_the_doctor_queue():
    desk_login = client.post("/api/v1/auth/login", json={"email": "registration@clinic.com", "password": "password123"})
    assert desk_login.status_code == 200, desk_login.text
    desk = {"Authorization": f"Bearer {desk_login.json()['access_token']}"}
    created = client.post("/api/v1/patients", headers=desk, json={"name": "Desk Narayan", "age": "34", "sex": "Male", "contact": "9999900013"})
    assert created.status_code == 201, created.text
    doctor = _login()
    waiting = client.get("/api/v1/dashboard", headers=doctor)
    assert waiting.status_code == 200, waiting.text
    listed = {item["patient_name"]: item for item in waiting.json()["today"]["consultations"]}
    assert listed["Desk Narayan"]["status"] == "arrived"
    assert listed["Desk Narayan"]["kind"] == "new"
    assert listed["Desk Narayan"]["channel"] == "walk_in"
    checked = client.post("/api/v1/queue/check-in", headers=desk, json={
        "patient_id": created.json()["id"],
        "channel": "online",
        "kind": "revisit",
    })
    assert checked.status_code == 200, checked.text
    assert checked.json()["token_number"]
    again = client.get("/api/v1/dashboard", headers=doctor)
    row = {item["patient_name"]: item for item in again.json()["today"]["consultations"]}["Desk Narayan"]
    assert row["kind"] == "revisit"
    assert row["channel"] == "online"
    assert row["status"] == "arrived"
    assert row["visit_id"] == checked.json()["visit_id"]


def test_temporary_booking_gets_a_permanent_mrd_at_registration_and_can_be_cancelled():
    doctor = _login()
    booked = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Temp Booking",
        "age": "30",
        "sex": "Male",
        "temporary": True,
    })
    assert booked.status_code == 201, booked.text
    temp_id = booked.json()["mrd_number"]
    assert temp_id.startswith("TMP-")
    assert booked.json()["registration_status"] == "temporary"
    day = client.get("/api/v1/dashboard", headers=doctor).json()["today"]["date"]
    appointment = client.post("/api/v1/appointments", headers=doctor, json={
        "patient_id": booked.json()["id"],
        "scheduled_at": f"{day}T16:00:00",
        "channel": "in_clinic",
    })
    assert appointment.status_code == 201, appointment.text
    cancelled_slot = client.patch(
        f"/api/v1/appointments/{appointment.json()['id']}/status?status=cancelled",
        headers=doctor,
    )
    assert cancelled_slot.status_code == 200, cancelled_slot.text
    assert cancelled_slot.json()["status"] == "cancelled"
    registered = client.post(f"/api/v1/patients/{booked.json()['id']}/assign-mrd", headers=doctor)
    assert registered.status_code == 200, registered.text
    permanent = registered.json()["mrd_number"]
    assert permanent.startswith("MRD-")
    assert permanent != temp_id
    again = client.post(f"/api/v1/patients/{booked.json()['id']}/assign-mrd", headers=doctor)
    assert again.json()["mrd_number"] == permanent
    removed = client.post(f"/api/v1/patients/{booked.json()['id']}/cancel", headers=doctor)
    assert removed.status_code == 200, removed.text
    assert removed.json()["mrd_number"] in (None, "")
    listed = client.get("/api/v1/patients?q=Temp Booking", headers=doctor)
    assert all(item["id"] != booked.json()["id"] for item in listed.json())
    reused = client.post("/api/v1/patients", headers=doctor, json={"name": "Next Permanent", "age": "31", "sex": "Female"})
    assert reused.status_code == 201, reused.text
    from app.core.database import SessionLocal
    from app.models import Patient
    check = SessionLocal()
    try:
        holder = check.query(Patient).filter(Patient.mrd_number == permanent).one_or_none()
    finally:
        check.close()
    assert holder is None or holder.id == reused.json()["id"]


def test_registration_cancel_stops_after_a_printed_or_locked_visit():
    from datetime import datetime

    from app.core.database import SessionLocal
    from app.models import Visit

    doctor = _login()
    draft = client.post("/api/v1/patients", headers=doctor, json={"name": "Draft Cancel", "age": "40", "sex": "Male"})
    assert draft.status_code == 201, draft.text
    visit = client.post(f"/api/v1/patients/{draft.json()['id']}/visits", headers=doctor, json={
        "visit_type": "New Visit",
        "chief_complaints": "thirst",
    })
    assert visit.status_code == 201, visit.text
    allowed = client.post(f"/api/v1/patients/{draft.json()['id']}/cancel", headers=doctor)
    assert allowed.status_code == 200, allowed.text

    printed = client.post("/api/v1/patients", headers=doctor, json={"name": "Printed Chart", "age": "41", "sex": "Female"})
    printed_visit = client.post(f"/api/v1/patients/{printed.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    assert printed_visit.status_code == 201, printed_visit.text
    db = SessionLocal()
    try:
        row = db.get(Visit, printed_visit.json()["id"])
        row.pdf_generated_at = datetime(2026, 11, 19, 9, 0, 0)
        db.commit()
    finally:
        db.close()
    refused_print = client.post(f"/api/v1/patients/{printed.json()['id']}/cancel", headers=doctor)
    assert refused_print.status_code == 400, refused_print.text
    assert "printed" in refused_print.json()["detail"]

    locked = client.post("/api/v1/patients", headers=doctor, json={"name": "Locked Chart", "age": "42", "sex": "Male"})
    locked_visit = client.post(f"/api/v1/patients/{locked.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    assert locked_visit.status_code == 201, locked_visit.text
    db = SessionLocal()
    try:
        row = db.get(Visit, locked_visit.json()["id"])
        row.status = "locked"
        row.finalized_at = datetime(2026, 11, 19, 9, 30, 0)
        db.commit()
    finally:
        db.close()
    refused_lock = client.post(f"/api/v1/patients/{locked.json()['id']}/cancel", headers=doctor)
    assert refused_lock.status_code == 400, refused_lock.text
    assert "locked" in refused_lock.json()["detail"]


def test_cancelling_the_calendar_slot_cancels_the_follow_up():
    doctor = _login()
    phone = f"94{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Calendar Followup", "age": "44", "sex": "Female", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={
        "visit_type": "New Visit",
        "follow_up_date": "2026-12-15",
    })
    assert visit.status_code == 201, visit.text
    listed = client.get("/api/v1/appointments", headers=doctor)
    linked = next(row for row in listed.json() if f"visit #{visit.json()['id']}" in (row.get("notes") or ""))
    cancelled = client.patch(f"/api/v1/appointments/{linked['id']}/status?status=cancelled", headers=doctor)
    assert cancelled.status_code == 200, cancelled.text
    queue = client.get("/api/v1/follow-ups?scope=all&days=180", headers=doctor)
    assert queue.status_code == 200, queue.text
    row = next(item for item in queue.json() if item["visit_id"] == visit.json()["id"])
    assert row["bucket"] == "cancelled"
    upcoming = client.get("/api/v1/follow-ups?scope=upcoming&days=180", headers=doctor)
    assert all(item["visit_id"] != visit.json()["id"] for item in upcoming.json())


def test_calendar_done_and_a_cancelled_reminder_update_the_follow_up():
    doctor = _login()
    phone = f"93{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Synced Followup", "age": "51", "sex": "Male", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={
        "visit_type": "New Visit",
        "follow_up_date": "2026-12-18",
    })
    assert visit.status_code == 201, visit.text
    listed = client.get("/api/v1/appointments", headers=doctor)
    linked = next(row for row in listed.json() if f"visit #{visit.json()['id']}" in (row.get("notes") or ""))
    moved = client.patch(
        f"/api/v1/appointments/{linked['id']}",
        headers=doctor,
        json={"scheduled_at": "2026-12-22T11:00:00"},
    )
    assert moved.status_code == 200, moved.text
    queue = client.get("/api/v1/follow-ups?scope=all&days=180", headers=doctor)
    row = next(item for item in queue.json() if item["visit_id"] == visit.json()["id"])
    assert row["follow_up_date"].startswith("2026-12-22")
    done = client.patch(f"/api/v1/appointments/{linked['id']}/status?status=completed", headers=doctor)
    assert done.status_code == 200, done.text
    queue = client.get("/api/v1/follow-ups?scope=all&days=180", headers=doctor)
    row = next(item for item in queue.json() if item["visit_id"] == visit.json()["id"])
    assert row["bucket"] == "done"

    overdue = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={
        "visit_type": "New Visit",
        "follow_up_date": "2026-12-28",
    })
    assert overdue.status_code == 201, overdue.text
    from app.models import Appointment, Visit
    db = SessionLocal()
    try:
        stored = db.get(Visit, overdue.json()["id"])
        stored.follow_up_date = date(2026, 10, 2)
        for slot in db.query(Appointment).filter(Appointment.notes.like(f"%visit #{stored.id}%")).all():
            slot.scheduled_at = datetime(2026, 10, 2, 10, 0)
        db.commit()
    finally:
        db.close()
    reminders = client.get("/api/v1/reminders/queue?days=3", headers=doctor)
    assert reminders.status_code == 200, reminders.text
    assert any(
        item["source_type"] == "follow_up" and item["source_id"] == overdue.json()["id"]
        for item in reminders.json()
    )
    cancelled = client.post("/api/v1/reminders/cancel", headers=doctor, json={
        "source_type": "follow_up",
        "source_id": overdue.json()["id"],
    })
    assert cancelled.status_code == 200, cancelled.text
    queue = client.get("/api/v1/follow-ups?scope=all&days=180", headers=doctor)
    row = next(item for item in queue.json() if item["visit_id"] == overdue.json()["id"])
    assert row["bucket"] == "cancelled"
    reminders = client.get("/api/v1/reminders/queue?days=3", headers=doctor)
    assert all(item["source_id"] != overdue.json()["id"] or item["source_type"] != "follow_up" for item in reminders.json())


def test_reschedule_moves_the_existing_follow_up_appointment():
    doctor = _login()
    patient = client.post("/api/v1/patients", headers=doctor, json={"name": "Move Followup", "age": "50", "sex": "Female"})
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={
        "visit_type": "New Visit",
        "follow_up_date": "2026-12-01",
    })
    assert visit.status_code == 201, visit.text
    listed = client.get("/api/v1/appointments", headers=doctor)
    linked = [row for row in listed.json() if f"visit #{visit.json()['id']}" in (row.get("notes") or "")]
    assert linked, listed.text
    moved = client.patch(
        f"/api/v1/visits/{visit.json()['id']}/follow-up?follow_up_date=2026-12-20&follow_up_time=15:30",
        headers=doctor,
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["appointment_id"] == linked[0]["id"]
    again = client.get("/api/v1/appointments", headers=doctor)
    same = next(row for row in again.json() if row["id"] == linked[0]["id"])
    assert same["scheduled_at"].startswith("2026-12-20T15:30")
    assert same["status"] == "scheduled"


def test_a_new_doctor_gets_a_separate_setup_and_a_desk_can_switch():
    doctor = _login()
    existing = client.get("/api/v1/auth/me", headers=doctor)
    assert existing.status_code == 200, existing.text
    stamp = datetime.utcnow().strftime("%H%M%S%f")
    email = f"newdoc{stamp}@clinic.com"
    created = client.post("/api/v1/auth/register", headers=_login(), json={
        "email": email,
        "password": "password123",
        "display_name": "Separate Doctor",
        "qualifications": "MD",
        "kmc_number": "KMCNEW",
    })
    assert created.status_code == 201, created.text
    assert created.json()["clinic_id"] != existing.json()["clinic_id"]
    tokens = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert tokens.status_code == 200, tokens.text
    new_headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    profile = client.get("/api/v1/clinic/profile", headers=new_headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["name"] == "Separate Doctor"
    assert profile.json()["clinic_id"] != existing.json()["clinic_id"]
    own_patients = client.get("/api/v1/patients", headers=new_headers)
    assert own_patients.status_code == 200, own_patients.text
    assert own_patients.json() == []
    refused = client.patch("/api/v1/auth/acting-doctor", headers=new_headers, json={"doctor_id": existing.json()["id"]})
    assert refused.status_code == 403, refused.text
    desk = client.post("/api/v1/auth/login", json={"email": "billing@clinic.com", "password": "password123"})
    assert desk.status_code == 200, desk.text
    desk_headers = {"Authorization": f"Bearer {desk.json()['access_token']}"}
    doctors = client.get("/api/v1/auth/doctors", headers=desk_headers)
    assert doctors.status_code == 200, doctors.text
    assert any(row["id"] == created.json()["id"] for row in doctors.json())
    try:
        switched = client.patch("/api/v1/auth/acting-doctor", headers=desk_headers, json={"doctor_id": created.json()["id"]})
        assert switched.status_code == 200, switched.text
        assert switched.json()["acting_clinic_id"] == created.json()["clinic_id"]
        seen = client.get("/api/v1/patients", headers=desk_headers)
        assert seen.json() == []
        letterhead = client.get("/api/v1/clinic/profile", headers=desk_headers)
        assert letterhead.json()["name"] == "Separate Doctor"
    finally:
        client.patch("/api/v1/auth/acting-doctor", headers=desk_headers, json={"doctor_id": existing.json()["id"]})


def test_registration_files_a_patient_under_the_chosen_doctor():
    stamp = datetime.utcnow().strftime("%H%M%S%f")
    email = f"chosendoc{stamp}@clinic.com"
    created = client.post("/api/v1/auth/register", headers=_login(), json={
        "email": email,
        "password": "password123",
        "display_name": "Chosen Doctor",
    })
    assert created.status_code == 201, created.text
    desk = client.post("/api/v1/auth/login", json={"email": "registration@clinic.com", "password": "password123"})
    assert desk.status_code == 200, desk.text
    desk_headers = {"Authorization": f"Bearer {desk.json()['access_token']}"}
    missing = client.post("/api/v1/patients", headers=desk_headers, json={
        "name": "No Doctor", "age": "30", "sex": "Male", "contact": f"91{stamp[:8]}", "doctor_id": 999999,
    })
    assert missing.status_code == 400, missing.text
    phone = f"92{stamp[:8]}"
    patient = client.post("/api/v1/patients", headers=desk_headers, json={
        "name": "Filed Patient", "age": "33", "sex": "Female", "contact": phone,
        "doctor_id": created.json()["id"],
    })
    assert patient.status_code == 201, patient.text
    assert patient.json()["doctor_id"] == created.json()["id"]
    assert patient.json()["clinic_id"] == created.json()["clinic_id"]
    queued = client.post("/api/v1/queue/check-in", headers=desk_headers, json={
        "patient_id": patient.json()["id"],
        "channel": "walk_in",
        "kind": "new",
        "doctor_id": created.json()["id"],
    })
    assert queued.status_code == 200, queued.text
    tokens = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    new_headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    visible = client.get(f"/api/v1/patients/{patient.json()['id']}", headers=new_headers)
    assert visible.status_code == 200, visible.text
    other = _login()
    hidden = client.get(f"/api/v1/patients/{patient.json()['id']}", headers=other)
    assert hidden.status_code == 404, hidden.text


def test_registration_search_sees_every_doctor_and_can_assign_one():
    stamp = datetime.utcnow().strftime("%H%M%S%f")
    first = client.post("/api/v1/auth/register", headers=_login(), json={
        "email": f"searchdoc{stamp}@clinic.com",
        "password": "password123",
        "display_name": "Search Doctor",
    })
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/auth/register", headers=_login(), json={
        "email": f"assigndoc{stamp}@clinic.com",
        "password": "password123",
        "display_name": "Assign Doctor",
    })
    assert second.status_code == 201, second.text
    owner = client.post("/api/v1/auth/login", json={"email": first.json()["email"], "password": "password123"})
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
    phone = f"93{stamp[:8]}"
    made = client.post("/api/v1/patients", headers=owner_headers, json={
        "name": f"Shared Search {stamp[-4:]}", "age": "41", "sex": "Male", "contact": phone,
    })
    assert made.status_code == 201, made.text
    desk = client.post("/api/v1/auth/login", json={"email": "registration@clinic.com", "password": "password123"})
    desk_headers = {"Authorization": f"Bearer {desk.json()['access_token']}"}
    found = client.get(f"/api/v1/patients?q={made.json()['name']}&search_type=name", headers=desk_headers)
    assert found.status_code == 200, found.text
    assert any(row["id"] == made.json()["id"] for row in found.json())
    assigned = client.post("/api/v1/queue/check-in", headers=desk_headers, json={
        "patient_id": made.json()["id"],
        "channel": "walk_in",
        "kind": "revisit",
        "doctor_id": second.json()["id"],
    })
    assert assigned.status_code == 200, assigned.text
    moved = client.get(f"/api/v1/patients/{made.json()['id']}", headers=desk_headers)
    assert moved.json()["doctor_id"] == second.json()["id"]
    assert moved.json()["clinic_id"] == second.json()["clinic_id"]
    new_owner = client.post("/api/v1/auth/login", json={"email": second.json()["email"], "password": "password123"})
    visible = client.get(
        f"/api/v1/patients/{made.json()['id']}",
        headers={"Authorization": f"Bearer {new_owner.json()['access_token']}"},
    )
    assert visible.status_code == 200, visible.text


def test_pharmacy_can_decline_a_dispense_with_a_note():
    doctor = _login()
    me = client.get("/api/v1/auth/me", headers=doctor)
    phone = f"91{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Outside Pharmacy", "age": "58", "sex": "Female", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    assert visit.status_code == 201, visit.text
    rx = client.post(f"/api/v1/visits/{visit.json()['id']}/prescriptions", headers=doctor, json={
        "custom_drug_name": "Metformin",
        "dosage": "500 mg",
        "frequency": "Once daily",
        "duration": "30 days",
    })
    assert rx.status_code == 201, rx.text
    pharmacy = client.post("/api/v1/auth/login", json={"email": "pharmacy@clinic.com", "password": "password123"})
    assert pharmacy.status_code == 200, pharmacy.text
    headers = {"Authorization": f"Bearer {pharmacy.json()['access_token']}"}
    client.patch("/api/v1/auth/acting-doctor", headers=headers, json={"doctor_id": me.json()["id"]})
    short = client.post("/api/v1/pharmacy/prescriptions/decline", headers=headers, json={
        "visit_id": visit.json()["id"], "note": "no",
    })
    assert short.status_code == 400, short.text
    declined = client.post("/api/v1/pharmacy/prescriptions/decline", headers=headers, json={
        "visit_id": visit.json()["id"],
        "note": "Patient will buy the medicines outside the clinic",
    })
    assert declined.status_code == 200, declined.text
    queue = client.get("/api/v1/pharmacy/prescriptions", headers=headers)
    assert queue.status_code == 200, queue.text
    row = next(item for item in queue.json() if item["visit_id"] == visit.json()["id"])
    assert row["declined"] is True
    assert "outside" in (row.get("dispense_note") or "")


def test_the_same_mobile_cannot_be_registered_twice():
    doctor = _login()
    first = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Mobile Owner", "age": "40", "sex": "Female", "contact": "9999922222",
    })
    assert first.status_code == 201, first.text
    again = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Someone Else", "age": "22", "sex": "Male", "contact": "9999922222",
    })
    assert again.status_code == 400, again.text
    assert "Mobile Owner" in again.json()["detail"]
    extra = client.post("/api/v1/messages/contacts", headers=doctor, json={"name": "Copy", "phone": "9999922222"})
    assert extra.status_code == 400, extra.text
    assert "Mobile Owner" in extra.json()["detail"]
    saved = client.post("/api/v1/messages/contacts", headers=doctor, json={"name": "Neighbour", "phone": "9999933333"})
    assert saved.status_code == 201, saved.text
    repeat = client.post("/api/v1/messages/contacts", headers=doctor, json={"name": "Neighbour Again", "phone": "9999933333"})
    assert repeat.status_code == 400, repeat.text
    assert "Neighbour" in repeat.json()["detail"]


def test_the_test_list_does_not_use_patient_numbers():
    doctor = _login()
    added = client.post("/api/v1/messages/contacts", headers=doctor, json={
        "name": "My phone", "phone": "9811111111", "list_kind": "test",
    })
    assert added.status_code == 201, added.text
    assert added.json()["list_kind"] == "test"
    again = client.post("/api/v1/messages/contacts", headers=doctor, json={
        "name": "My phone again", "phone": "9811111111", "list_kind": "test",
    })
    assert again.status_code == 400, again.text
    trial = client.post("/api/v1/messages/broadcast", headers=doctor, json={
        "kind": "greeting", "message": "Test {name}", "audience": "test",
    })
    assert trial.status_code == 200, trial.text
    body = trial.json()
    assert body["audience"] == 1
    assert body["items"][0]["name"] == "My phone"
    assert str(body["items"][0]["phone"]).endswith("9811111111")
    patients = client.post("/api/v1/messages/broadcast", headers=doctor, json={"kind": "greeting", "message": "Hello {name}"})
    assert patients.status_code == 200, patients.text
    assert patients.json()["audience"] >= 1
    assert all(not str(row["phone"]).endswith("9811111111") for row in patients.json()["items"])


def test_a_short_number_is_not_opened_in_whatsapp():
    doctor = _login()
    bad = client.post("/api/v1/messages/send-text", headers=doctor, json={
        "phone": "12", "name": "Test", "kind": "greeting", "message": "Hello",
    })
    assert bad.status_code == 400, bad.text


def test_saved_numbers_are_kept_for_the_next_message():
    doctor = _login()
    saved = client.post("/api/v1/messages/contacts", headers=doctor, json={"name": "Aunty Rao", "phone": "9999901234"})
    assert saved.status_code == 201, saved.text
    again = client.get("/api/v1/messages/contacts", headers=doctor)
    assert again.status_code == 200, again.text
    assert any(row["name"] == "Aunty Rao" and row["phone"] == "9999901234" for row in again.json())
    sent = client.post("/api/v1/messages/broadcast", headers=doctor, json={"kind": "greeting", "message": "Hello {name}"})
    assert sent.status_code == 200, sent.text
    match = next(row for row in sent.json()["items"] if str(row["phone"]).endswith("9999901234"))
    assert match["name"] == "Aunty Rao"
    assert "wa.me" in (match["whatsapp_url"] or "")


def test_uploaded_video_is_shared_with_every_patient():
    doctor = _login()
    uploaded = client.post(
        "/api/v1/messages/videos",
        headers=doctor,
        files={"file": ("walk.mp4", b"0" * 1200, "video/mp4")},
        data={"title": "Walk after meals"},
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["url"].endswith(body["token"])
    played = client.get(f"/api/v1/messages/videos/{body['token']}")
    assert played.status_code == 200, played.text
    assert played.content == b"0" * 1200
    sent = client.post("/api/v1/messages/broadcast", headers=doctor, json={
        "kind": "video",
        "video_title": "Walk after meals",
        "video_url": body["url"],
    })
    assert sent.status_code == 200, sent.text
    assert sent.json()["audience"] >= 1
    assert body["token"] in sent.json()["items"][0]["whatsapp_url"]


def test_returning_patient_search_and_clinic_broadcast():
    doctor = _login()
    created = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Old Chart Rao", "age": "61", "sex": "Male", "contact": "9999912345",
    })
    assert created.status_code == 201, created.text
    found = client.get("/api/v1/patients?q=9999912345&search_type=phone", headers=doctor)
    assert found.status_code == 200, found.text
    assert any(row["name"] == "Old Chart Rao" for row in found.json())
    desk = client.post("/api/v1/auth/login", json={"email": "registration@clinic.com", "password": "password123"})
    assert desk.status_code == 200, desk.text
    registration = {"Authorization": f"Bearer {desk.json()['access_token']}"}
    hidden = client.get("/api/v1/patients?q=diabetes&search_type=diagnosis", headers=registration)
    assert hidden.status_code == 403
    sent = client.post("/api/v1/messages/broadcast", headers=registration, json={
        "kind": "greeting",
        "message": "Warm wishes from {clinic}.",
    })
    assert sent.status_code == 200, sent.text
    match = next(row for row in sent.json()["items"] if row["name"] == "Old Chart Rao")
    assert match["whatsapp_url"].startswith("https://wa.me/")
    assert "Old Chart Rao" in match["whatsapp_url"] or "Namaste" in match["whatsapp_url"]
    video = client.post("/api/v1/messages/broadcast", headers=registration, json={
        "kind": "video",
        "video_title": "Walking after meals",
        "video_url": "https://youtu.be/example",
    })
    assert video.status_code == 200, video.text
    assert "youtu.be" in video.json()["items"][0]["whatsapp_url"]


def test_a_clinic_message_stays_out_of_the_reminder_log():
    doctor = _login()
    sent = client.post("/api/v1/messages/broadcast", headers=doctor, json={"kind": "greeting", "message": "Hello {name}"})
    assert sent.status_code == 200, sent.text
    history = client.get("/api/v1/reminders/history", headers=doctor)
    assert history.status_code == 200, history.text
    assert all(row["source_type"] != "broadcast" for row in history.json())


def test_reminder_names_can_be_changed_and_a_reminder_can_be_cancelled():
    doctor = _login()
    before = client.get("/api/v1/reminders/status", headers=doctor)
    assert before.status_code == 200, before.text
    phone = f"95{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Remind Rao", "age": "40", "sex": "Male", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    when = (date.today() + timedelta(days=1)).isoformat()
    booked = client.post("/api/v1/appointments", headers=doctor, json={
        "patient_id": patient.json()["id"],
        "scheduled_at": f"{when}T10:00:00",
        "channel": "in_clinic",
    })
    assert booked.status_code == 201, booked.text
    named = client.patch("/api/v1/reminders/names", headers=doctor, json={
        "clinic_name": "Lake Clinic",
        "doctor_name": "Vishwanath S",
    })
    assert named.status_code == 200, named.text
    queue = client.get("/api/v1/reminders/queue?days=3", headers=doctor)
    assert queue.status_code == 200, queue.text
    row = next(item for item in queue.json() if item["patient_name"] == "Remind Rao")
    assert "Lake Clinic" in row["message"]
    assert "Vishwanath S" in row["message"]
    cancelled = client.post("/api/v1/reminders/cancel", headers=doctor, json={
        "source_type": "appointment",
        "source_id": booked.json()["id"],
    })
    assert cancelled.status_code == 200, cancelled.text
    again = client.get("/api/v1/reminders/queue?days=3", headers=doctor)
    assert all(item["source_id"] != booked.json()["id"] or item["source_type"] != "appointment" for item in again.json())
    client.patch("/api/v1/reminders/names", headers=doctor, json={
        "clinic_name": before.json()["clinic_name"],
        "doctor_name": before.json().get("doctor_name") or "Doctor",
    })


def test_endocrine_templates_and_a_nurse_chart():
    from app.services.specialty_templates import list_template_options
    ids = {row["id"] for row in list_template_options()}
    for key in ("diabetic_foot", "gestational", "pediatric", "obesity", "bone"):
        assert key in ids
    doctor = _login()
    email = f"nurse{datetime.utcnow().strftime('%H%M%S%f')[:8]}@clinic.com"
    created = client.post("/api/v1/auth/staff", headers=doctor, json={
        "email": email, "password": "password123", "display_name": "Ward Nurse", "role": "nurse",
    })
    assert created.status_code == 201, created.text
    nurse = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert nurse.status_code == 200, nurse.text
    headers = {"Authorization": f"Bearer {nurse.json()['access_token']}"}
    phone = f"89{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Nurse Chart", "age": "40", "sex": "Female", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    chart = client.get(f"/api/v1/patients/{patient.json()['id']}", headers=headers)
    assert chart.status_code == 200, chart.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=headers, json={
        "visit_type": "New Visit",
        "specialty_template": "diabetic_foot",
        "specialty_data": {"foot_risk": "Moderate"},
    })
    assert visit.status_code == 201, visit.text
    blocked = client.post(f"/api/v1/visits/{visit.json()['id']}/prescriptions", headers=headers, json={
        "custom_drug_name": "Metformin", "dosage": "500 mg", "frequency": "Once daily", "duration": "30 days",
    })
    assert blocked.status_code == 403, blocked.text


def test_lab_results_are_shared_across_the_chart():
    doctor = _login()
    phone = f"88{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Lab Share Rao", "age": "52", "sex": "Male", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    pid = patient.json()["id"]
    created = client.post(f"/api/v1/patients/{pid}/visits", headers=doctor, json={
        "visit_type": "New Visit",
        "diagnosis": "Type 2 diabetes mellitus",
        "investigation": "TSH 4.2 mIU/L\nReviewed the previous notes",
        "ordered_investigations": "Lipid profile",
        "specialty_template": "diabetes",
        "specialty_data": {"hba1c": "8.1", "lipid_ldl": "140"},
    })
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]
    labs = client.get(f"/api/v1/patients/{pid}/labs", headers=doctor)
    assert labs.status_code == 200, labs.text
    names = [row["test_name"] for row in labs.json()]
    assert names.count("HbA1c") == 1
    assert names.count("TSH") == 1
    assert names.count("LDL") == 1
    assert "Lipid profile" not in names
    updated = client.patch(f"/api/v1/visits/{visit_id}", headers=doctor, json={
        "visit_type": "New Visit",
        "diagnosis": "Type 2 diabetes mellitus",
        "investigation": "TSH 5.1",
        "ordered_investigations": "Lipid profile",
        "specialty_template": "diabetes",
        "specialty_data": {"hba1c": "7.4", "lipid_ldl": "140"},
    })
    assert updated.status_code == 200, updated.text
    labs = client.get(f"/api/v1/patients/{pid}/labs", headers=doctor)
    by_name = {}
    for row in labs.json():
        by_name.setdefault(row["test_name"], []).append(row["value"])
    assert by_name["HbA1c"] == ["7.4"]
    assert by_name["TSH"] == ["5.1"]
    alias = client.post(f"/api/v1/patients/{pid}/labs", headers=doctor, json={
        "test_name": "Glycated hemoglobin", "value": "7.9",
    })
    assert alias.status_code == 201, alias.text
    dash = client.get(f"/api/v1/patients/{pid}/diabetes-dashboard", headers=doctor)
    assert dash.status_code == 200, dash.text
    trend = [row["value"] for row in dash.json()["hba1c_trend"]]
    assert "7.4" in trend and "7.9" in trend
    recent = {row["test_name"]: row["value"] for row in dash.json()["recent_labs"]}
    assert recent["HbA1c"] == "7.9"
    assert recent["TSH"] == "5.1"
    assert recent["LDL"] == "140"
    lipids = next(row for row in dash.json()["screening"] if row["item"] == "lipids")
    assert lipids["last_on"]
    observed = client.post(f"/api/v1/patients/{pid}/observations", headers=doctor, json={
        "observation_code": "uacr",
        "observation_name": "Urine albumin-creatinine ratio",
        "value_text": "42",
        "unit": "mg/g",
        "observed_at": "2026-11-21",
        "source": "laboratory_report",
    })
    assert observed.status_code == 201, observed.text
    dash = client.get(f"/api/v1/patients/{pid}/diabetes-dashboard", headers=doctor)
    kidney = next(row for row in dash.json()["screening"] if row["item"] == "nephropathy")
    assert kidney["last_on"] == "2026-11-21"
    labs = client.get(f"/api/v1/patients/{pid}/labs", headers=doctor)
    assert any(row["test_name"] == "Urine albumin-creatinine ratio" and row["value"] == "42" for row in labs.json())
    timeline = client.get(f"/api/v1/patients/{pid}/timeline", headers=doctor)
    assert "HbA1c" in timeline.json()["labs"]


def test_a_cancelled_registration_is_not_left_waiting():
    doctor = _login()
    phone = f"96{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Cancel Queue Rao", "age": "65", "sex": "Male", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    patient_id = patient.json()["id"]
    checked = client.post("/api/v1/queue/check-in", headers=doctor, json={
        "patient_id": patient_id, "channel": "walk_in", "kind": "new",
    })
    assert checked.status_code == 200, checked.text
    billed = client.post("/api/v1/bills", headers=doctor, json={
        "visit_id": checked.json()["visit_id"],
        "category": "consultation",
        "payment_status": "paid",
        "payment_method": "Cash",
        "line_items": [{"description": "Consultation", "quantity": 1, "rate": 800, "gst_percent": 0}],
    })
    assert billed.status_code == 201, billed.text
    cancelled = client.post(f"/api/v1/patients/{patient_id}/cancel", headers=doctor)
    assert cancelled.status_code == 200, cancelled.text
    board = client.get("/api/v1/dashboard", headers=doctor)
    assert board.status_code == 200, board.text
    row = next(item for item in board.json()["today"]["consultations"] if item["patient_name"] == "Cancel Queue Rao")
    assert row["status"] == "registration_cancelled"
    assert cancelled.json()["mrd_number"] in (None, "")
    listed = client.get("/api/v1/appointments", headers=doctor)
    assert listed.status_code == 200, listed.text
    booked = [item for item in listed.json() if item["patient_name"] == "Cancel Queue Rao"]
    assert booked and all(item["status"] == "cancelled" for item in booked)
    waiting = [item for item in board.json()["today"]["consultations"] if item["status"] in {"arrived", "scheduled", "due"}]
    assert all(item["patient_name"] != "Cancel Queue Rao" for item in waiting)


def test_appointment_cancel_keeps_the_mrd_and_registration():
    doctor = _login()
    phone = f"90{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    name = f"Slot Only {datetime.utcnow().strftime('%H%M%S%f')[:6]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": name, "age": "54", "sex": "Male", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    mrd = patient.json()["mrd_number"]
    checked = client.post("/api/v1/queue/check-in", headers=doctor, json={
        "patient_id": patient.json()["id"], "channel": "walk_in", "kind": "new",
    })
    assert checked.status_code == 200, checked.text
    appointment_id = checked.json()["appointment_id"]
    cancelled_slot = client.patch(
        f"/api/v1/appointments/{appointment_id}/status?status=cancelled",
        headers=doctor,
    )
    assert cancelled_slot.status_code == 200, cancelled_slot.text
    chart = client.get(f"/api/v1/patients/{patient.json()['id']}", headers=doctor)
    assert chart.status_code == 200, chart.text
    assert chart.json()["mrd_number"] == mrd
    assert chart.json()["registration_status"] == "active"
    board = client.get("/api/v1/dashboard", headers=doctor)
    row = next(item for item in board.json()["today"]["consultations"] if item["patient_id"] == patient.json()["id"])
    assert row["status"] == "appointment_cancelled"
    assert row["patient_mrd"] == mrd
    chart_appts = client.get(f"/api/v1/patients/{patient.json()['id']}/appointments", headers=doctor)
    assert chart_appts.status_code == 200, chart_appts.text
    assert any(item["id"] == appointment_id and item["status"] == "cancelled" for item in chart_appts.json())
    visit = next(item for item in chart.json()["visits"] if item["id"] == checked.json()["visit_id"])
    assert visit["status"] == "cancelled"
    removed = client.post(f"/api/v1/patients/{patient.json()['id']}/cancel", headers=doctor)
    assert removed.status_code == 200, removed.text
    assert removed.json()["mrd_number"] in (None, "")
    again = client.get("/api/v1/dashboard", headers=doctor)
    closed = next(item for item in again.json()["today"]["consultations"] if item["patient_id"] == patient.json()["id"])
    assert closed["status"] == "registration_cancelled"


def test_a_saved_invoice_can_be_opened_later():
    doctor = _login()
    phone = f"97{datetime.utcnow().strftime('%H%M%S%f')[:8]}"
    patient = client.post("/api/v1/patients", headers=doctor, json={
        "name": "Later Bill", "age": "65", "sex": "Male", "contact": phone,
    })
    assert patient.status_code == 201, patient.text
    visit = client.post(f"/api/v1/patients/{patient.json()['id']}/visits", headers=doctor, json={"visit_type": "New Visit"})
    assert visit.status_code == 201, visit.text
    billed = client.post("/api/v1/bills", headers=doctor, json={
        "visit_id": visit.json()["id"],
        "category": "consultation",
        "payment_status": "paid",
        "payment_method": "Cash",
        "line_items": [{"description": "Consultation", "quantity": 1, "rate": 800, "gst_percent": 0}],
    })
    assert billed.status_code == 201, billed.text
    bill_id = billed.json()["id"]
    billing = client.post("/api/v1/auth/login", json={"email": "billing@clinic.com", "password": "password123"})
    assert billing.status_code == 200, billing.text
    desk = {"Authorization": f"Bearer {billing.json()['access_token']}"}
    opened = client.get(f"/api/v1/bills/{bill_id}", headers=desk)
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["invoice_number"]
    assert body["line_items"][0]["description"] == "Consultation"
    assert body["amount"] == 800
    assert body["receipts"][0]["method"] == "Cash"
    assert body["receipts"][0]["amount"] == 800
    history = client.get(f"/api/v1/commerce/patients/{patient.json()['id']}/bills", headers=desk)
    assert history.status_code == 200, history.text
    assert any(row["id"] == bill_id for row in history.json())


def test_only_a_doctor_can_store_qualifications_and_kmc():
    billing = client.post("/api/v1/auth/login", json={"email": "billing@clinic.com", "password": "password123"})
    assert billing.status_code == 200, billing.text
    desk = {"Authorization": f"Bearer {billing.json()['access_token']}"}
    updated = client.patch("/api/v1/auth/profile", headers=desk, json={
        "display_name": "Billing Desk",
        "qualifications": "MBBS",
        "kmc_number": "KMC-999",
    })
    assert updated.status_code == 200, updated.text
    assert not updated.json().get("qualifications")
    assert not updated.json().get("kmc_number")
    doctor = _login()
    me = client.get("/api/v1/auth/me", headers=doctor)
    assert me.status_code == 200, me.text
    kept = client.patch("/api/v1/auth/profile", headers=doctor, json={
        "display_name": me.json()["display_name"],
        "qualifications": "MBBS, MD (Endocrinology)",
        "kmc_number": "KMC-12345",
    })
    assert kept.status_code == 200, kept.text
    assert kept.json()["kmc_number"] == "KMC-12345"
    assert kept.json()["qualifications"] == "MBBS, MD (Endocrinology)"


if __name__ == "__main__":
    test_purchase_posts_stock_and_refuses_a_duplicate_invoice()
    test_expired_stock_cannot_be_dispensed_and_damaged_returns_stay_in_quarantine()
    test_split_collection_and_cash_drawer()
    test_outstanding_receipt_after_day_close_stays_on_the_new_day()
    test_only_a_doctor_or_admin_can_reopen_a_locked_day()
    test_today_queue_separates_new_walk_in_and_online_revisit()
    test_registration_sends_a_patient_to_the_doctor_queue()
    test_temporary_booking_gets_a_permanent_mrd_at_registration_and_can_be_cancelled()
    test_registration_cancel_stops_after_a_printed_or_locked_visit()
    test_reschedule_moves_the_existing_follow_up_appointment()
    print("commerce tests passed")
