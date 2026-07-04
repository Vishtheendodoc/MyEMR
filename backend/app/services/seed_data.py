"""Seed database with demo data on first startup."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    BrandMedication,
    Comorbidity,
    DrugComorbidityInteraction,
    GenericDrug,
    Patient,
    Prescription,
    User,
    Visit,
)
from app.services.medication_service import sync_medication_template


def seed_if_empty(db: Session):
    if db.query(GenericDrug).first():
        return False

    email = "demo@clinic.com"
    user = User(
        username=email,
        email=email,
        display_name="Demo Doctor",
        password=hash_password("password123"),
        role="doctor",
        qualifications="MBBS, MD (Endocrinology)",
        kmc_number="KMC-12345",
    )
    db.add(user)
    db.flush()

    comorbidities_data = [
        {"name": "Chronic Kidney Disease", "description": "Reduced kidney function", "severity": "high"},
        {"name": "Diabetic Nephropathy", "description": "Kidney damage from diabetes", "severity": "high"},
        {"name": "Hypertension", "description": "High blood pressure", "severity": "medium"},
        {"name": "Heart Failure", "description": "Reduced cardiac output", "severity": "high"},
        {"name": "Liver Disease", "description": "Impaired liver function", "severity": "high"},
        {"name": "Osteoporosis", "description": "Reduced bone density", "severity": "medium"},
        {"name": "Cardiovascular Disease", "description": "Heart and blood vessel disease", "severity": "high"},
    ]
    comorbidities = {}
    for data in comorbidities_data:
        c = Comorbidity(**data)
        db.add(c)
        db.flush()
        comorbidities[data["name"]] = c

    sync_medication_template(db)

    drugs_with_interactions = [
        ("Metformin", [
            ("Chronic Kidney Disease", "contraindicated", "high",
             "Avoid in severe CKD (eGFR <30). Risk of lactic acidosis."),
            ("Liver Disease", "caution", "high", "Use with caution. Risk of lactic acidosis."),
        ]),
        ("Empagliflozin", [
            ("Chronic Kidney Disease", "contraindicated", "high", "Not recommended if eGFR <20."),
            ("Heart Failure", "beneficial", "low", "Recommended in HFrEF."),
        ]),
        ("Levothyroxine", [
            ("Cardiovascular Disease", "caution", "high", "Start low dose and titrate slowly."),
        ]),
    ]
    for generic_name, interactions in drugs_with_interactions:
        generic = db.query(GenericDrug).filter_by(generic_name=generic_name).first()
        if not generic:
            continue
        for comorb_name, itype, severity, rec in interactions:
            if comorb_name in comorbidities:
                db.add(DrugComorbidityInteraction(
                    generic_drug_id=generic.id,
                    comorbidity_id=comorbidities[comorb_name].id,
                    interaction_type=itype,
                    severity=severity,
                    recommendation=rec,
                ))

    patients_data = [
        {"mrd_number": "MRD001", "name": "Ramesh Kumar", "age": "55", "sex": "Male",
         "contact": "9876543210", "address": "Mumbai, Maharashtra"},
        {"mrd_number": "MRD002", "name": "Priya Sharma", "age": "48", "sex": "Female",
         "contact": "9876543211", "address": "Delhi"},
        {"mrd_number": "MRD003", "name": "Suresh Patel", "age": "62", "sex": "Male",
         "contact": "9876543212", "address": "Gujarat"},
    ]
    patients = []
    for pdata in patients_data:
        p = Patient(doctor_id=user.id, **pdata)
        db.add(p)
        db.flush()
        patients.append(p)

    visit1 = Visit(
        patient_id=patients[0].id, doctor_id=user.id, visit_type="New Visit",
        chief_complaints="Increased thirst and frequent urination for 2 months",
        height=170.0, weight=78.0, bmi=27.0, bp_systolic=140, bp_diastolic=90,
        pulse=82, temperature=98.6, spo2=98,
        history="Diagnosed with Type 2 Diabetes 10 years ago.",
        examination="CVS: S1 S2 normal. RS: Clear.",
        diagnosis="Type 2 Diabetes Mellitus with Diabetic Nephropathy",
        comorbidities="Diabetic Nephropathy, Hypertension",
        investigation="HbA1c: 8.5%, eGFR: 45 ml/min",
        follow_up_date=(datetime.utcnow() + timedelta(days=30)).date(),
        follow_up_notes="Review HbA1c and kidney function.",
    )
    visit2 = Visit(
        patient_id=patients[1].id, doctor_id=user.id, visit_type="New Visit",
        chief_complaints="Fatigue and weight loss",
        height=162.0, weight=65.0, bmi=24.8, bp_systolic=120, bp_diastolic=80,
        pulse=76, diagnosis="Type 2 Diabetes Mellitus",
        investigation="HbA1c: 7.2%",
        follow_up_date=(datetime.utcnow() + timedelta(days=90)).date(),
    )
    db.add_all([visit1, visit2])
    db.flush()

    metformin = db.query(GenericDrug).filter_by(generic_name="Metformin").first()
    if metformin:
        brand = db.query(BrandMedication).filter_by(generic_drug_id=metformin.id).first()
        if brand:
            db.add(Prescription(
                visit_id=visit1.id, brand_medication_id=brand.id,
                dosage="500mg", frequency="BD", timing="1-0-1", duration="30 days",
                instructions="Take after meals",
            ))

    db.commit()
    return True
