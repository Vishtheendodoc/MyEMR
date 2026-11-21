"""Seed extended demo data for phases 2-5."""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    Bill,
    CgmReading,
    ImagingResult,
    LabResult,
    Patient,
    User,
    Visit,
)


def seed_extensions_if_missing(db: Session):
    if db.query(LabResult).first():
        return False

    user = db.query(User).filter_by(email="demo@clinic.com").first()
    if not user:
        return False

    patients = db.query(Patient).filter_by(doctor_id=user.id).all()
    if not patients:
        return False

    p1 = patients[0]
    visits = db.query(Visit).filter_by(patient_id=p1.id).all()
    visit1 = visits[0] if visits else None

    today = date.today()
    d90, d60, d30, d14, d0 = (
        today - timedelta(days=90),
        today - timedelta(days=60),
        today - timedelta(days=30),
        today - timedelta(days=14),
        today,
    )
    labs = [
        LabResult(patient_id=p1.id, visit_id=visit1.id if visit1 else None, test_name="HbA1c", value="8.5", unit="%", reference_range="4.0-5.6", result_date=d90),
        LabResult(patient_id=p1.id, test_name="HbA1c", value="8.1", unit="%", reference_range="4.0-5.6", result_date=d60),
        LabResult(patient_id=p1.id, test_name="HbA1c", value="7.8", unit="%", reference_range="4.0-5.6", result_date=d30),
        LabResult(patient_id=p1.id, test_name="HbA1c", value="7.2", unit="%", reference_range="4.0-5.6", result_date=d0),
        LabResult(patient_id=p1.id, test_name="eGFR", value="52", unit="mL/min", reference_range=">60", result_date=d90),
        LabResult(patient_id=p1.id, test_name="eGFR", value="48", unit="mL/min", reference_range=">60", result_date=d60),
        LabResult(patient_id=p1.id, test_name="eGFR", value="45", unit="mL/min", reference_range=">60", result_date=d30),
        LabResult(patient_id=p1.id, test_name="eGFR", value="47", unit="mL/min", reference_range=">60", result_date=d0),
        LabResult(patient_id=p1.id, test_name="TSH", value="2.8", unit="mIU/L", reference_range="0.4-4.5", result_date=d90),
        LabResult(patient_id=p1.id, test_name="TSH", value="2.1", unit="mIU/L", reference_range="0.4-4.5", result_date=d60),
        LabResult(patient_id=p1.id, test_name="TSH", value="1.9", unit="mIU/L", reference_range="0.4-4.5", result_date=d30),
        LabResult(patient_id=p1.id, test_name="FT4", value="1.1", unit="ng/dL", reference_range="0.8-1.8", result_date=d60),
        LabResult(patient_id=p1.id, test_name="FT4", value="1.2", unit="ng/dL", reference_range="0.8-1.8", result_date=d30),
        LabResult(patient_id=p1.id, test_name="Creatinine", value="1.4", unit="mg/dL", reference_range="0.6-1.2", result_date=d90),
        LabResult(patient_id=p1.id, test_name="Creatinine", value="1.5", unit="mg/dL", reference_range="0.6-1.2", result_date=d30),
        LabResult(patient_id=p1.id, test_name="Fasting Glucose", value="142", unit="mg/dL", reference_range="70-100", result_date=d14),
        LabResult(patient_id=p1.id, test_name="Fasting Glucose", value="128", unit="mg/dL", reference_range="70-100", result_date=d0),
    ]
    db.add_all(labs)

    if len(patients) > 1:
        p2 = patients[1]
        db.add_all([
            LabResult(patient_id=p2.id, test_name="HbA1c", value="7.2", unit="%", result_date=today - timedelta(days=45)),
            LabResult(patient_id=p2.id, test_name="TSH", value="5.8", unit="mIU/L", result_date=today - timedelta(days=20)),
        ])
        db.add(ImagingResult(patient_id=p2.id, study_type="Thyroid Ultrasound", findings="Enlarged thyroid with heterogeneous echotexture", report_date=today - timedelta(days=20)))

    db.add(ImagingResult(patient_id=p1.id, study_type="Renal Ultrasound", findings="Bilateral increased cortical echogenicity consistent with CKD", report_date=today - timedelta(days=60)))

    base_time = datetime.utcnow() - timedelta(hours=24)
    for i in range(48):
        db.add(CgmReading(
            patient_id=p1.id,
            glucose_mg_dl=100 + (i % 12) * 15 + (i % 3) * 20,
            reading_time=base_time + timedelta(minutes=i * 30),
            source="demo",
        ))

    for i, p in enumerate(patients[:2]):
        db.add(Appointment(
            patient_id=p.id,
            doctor_id=user.id,
            scheduled_at=datetime.utcnow() + timedelta(days=i + 1, hours=10),
            duration_minutes=20,
            status="scheduled",
            notes="Routine endocrine follow-up",
        ))

    if visit1:
        visit1.follow_up_date = today - timedelta(days=5)
        visit1.specialty_template = "diabetes"
        visit1.specialty_data = '{"fbs":"142","hba1c":"8.5","insulin_regimen":"Basal-bolus"}'
        db.add(Bill(
            visit_id=visit1.id,
            patient_id=p1.id,
            doctor_id=user.id,
            description="Consultation + HbA1c review",
            procedure_code="99213",
            amount=1500.0,
            payment_status="paid",
            payment_method="cash",
        ))
        db.add(Bill(
            visit_id=visit1.id,
            patient_id=p1.id,
            doctor_id=user.id,
            description="Lab panel",
            procedure_code="80053",
            amount=800.0,
            payment_status="pending",
        ))

    db.commit()
    return True
