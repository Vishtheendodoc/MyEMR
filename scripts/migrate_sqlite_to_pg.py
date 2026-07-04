#!/usr/bin/env python3
"""Migrate data from Flask SQLite database to PostgreSQL."""

import argparse
import os
import sqlite3
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    BrandMedication,
    Comorbidity,
    DiagnosisMaster,
    DrugComorbidityInteraction,
    GenericDrug,
    Patient,
    Prescription,
    User,
    Visit,
)

TABLES = [
    "user", "comorbidity", "diagnosis_master", "generic_drug",
    "patient", "brand_medication", "drug_comorbidity_interaction",
    "visit", "prescription",
]


def read_sqlite_rows(conn, table):
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def migrate(sqlite_path: str, pg_url: str, dry_run: bool = False):
    if not os.path.exists(sqlite_path):
        print(f"SQLite file not found: {sqlite_path}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(sqlite_path)
    counts_sqlite = {}
    for table in TABLES:
        try:
            counts_sqlite[table] = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts_sqlite[table] = 0

    print("SQLite row counts:")
    for t, c in counts_sqlite.items():
        print(f"  {t}: {c}")

    if dry_run:
        print("\nDry run — no data written.")
        return

    engine = create_engine(pg_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        db.execute(text("TRUNCATE prescription, visit, drug_comorbidity_interaction, brand_medication, patient, generic_drug, diagnosis_master, comorbidity, \"user\" RESTART IDENTITY CASCADE"))
        db.commit()

        id_maps = {}

        for row in read_sqlite_rows(sqlite_conn, "user"):
            old_id = row["id"]
            user = User(
                username=row["username"],
                email=row.get("email") or row["username"],
                display_name=row.get("display_name"),
                password=row["password"],
                role=row.get("role") or "doctor",
                qualifications=row.get("qualifications"),
                kmc_number=row.get("kmc_number"),
            )
            db.add(user)
            db.flush()
            id_maps.setdefault("user", {})[old_id] = user.id

        for row in read_sqlite_rows(sqlite_conn, "comorbidity"):
            old_id = row["id"]
            obj = Comorbidity(name=row["name"], description=row.get("description"), severity=row.get("severity"))
            db.add(obj)
            db.flush()
            id_maps.setdefault("comorbidity", {})[old_id] = obj.id

        for row in read_sqlite_rows(sqlite_conn, "diagnosis_master"):
            obj = DiagnosisMaster(
                diagnosis_name=row["diagnosis_name"],
                category=row.get("category"),
                icd_code=row.get("icd_code"),
                description=row.get("description"),
            )
            db.add(obj)

        for row in read_sqlite_rows(sqlite_conn, "generic_drug"):
            old_id = row["id"]
            obj = GenericDrug(
                generic_name=row["generic_name"],
                drug_class=row.get("drug_class"),
                indication=row.get("indication"),
            )
            db.add(obj)
            db.flush()
            id_maps.setdefault("generic_drug", {})[old_id] = obj.id

        for row in read_sqlite_rows(sqlite_conn, "patient"):
            old_id = row["id"]
            obj = Patient(
                mrd_number=row.get("mrd_number"),
                name=row["name"],
                age=row["age"],
                sex=row["sex"],
                contact=row.get("contact"),
                address=row.get("address"),
                date_registered=row.get("date_registered"),
                doctor_id=id_maps.get("user", {}).get(row.get("doctor_id")),
            )
            db.add(obj)
            db.flush()
            id_maps.setdefault("patient", {})[old_id] = obj.id

        for row in read_sqlite_rows(sqlite_conn, "brand_medication"):
            old_id = row["id"]
            obj = BrandMedication(
                brand_name=row["brand_name"],
                generic_drug_id=id_maps["generic_drug"][row["generic_drug_id"]],
                manufacturer=row.get("manufacturer"),
                strength=row.get("strength"),
                formulation=row.get("formulation"),
                price=row.get("price"),
            )
            db.add(obj)
            db.flush()
            id_maps.setdefault("brand_medication", {})[old_id] = obj.id

        for row in read_sqlite_rows(sqlite_conn, "drug_comorbidity_interaction"):
            db.add(DrugComorbidityInteraction(
                generic_drug_id=id_maps["generic_drug"][row["generic_drug_id"]],
                comorbidity_id=id_maps["comorbidity"][row["comorbidity_id"]],
                interaction_type=row["interaction_type"],
                recommendation=row.get("recommendation"),
                severity=row.get("severity"),
            ))

        for row in read_sqlite_rows(sqlite_conn, "visit"):
            old_id = row["id"]
            obj = Visit(
                patient_id=id_maps["patient"][row["patient_id"]],
                visit_date=row.get("visit_date"),
                visit_type=row.get("visit_type") or "New Visit",
                chief_complaints=row.get("chief_complaints"),
                height=row.get("height"),
                weight=row.get("weight"),
                bmi=row.get("bmi"),
                bp_systolic=row.get("bp_systolic"),
                bp_diastolic=row.get("bp_diastolic"),
                pulse=row.get("pulse"),
                temperature=row.get("temperature"),
                spo2=row.get("spo2"),
                history=row.get("history"),
                examination=row.get("examination"),
                diagnosis=row.get("diagnosis"),
                investigation=row.get("investigation"),
                comorbidities=row.get("comorbidities"),
                follow_up_date=row.get("follow_up_date"),
                follow_up_notes=row.get("follow_up_notes"),
                pdf_page_count=row.get("pdf_page_count"),
                pdf_generated_at=row.get("pdf_generated_at"),
                pdf_font_size=row.get("pdf_font_size"),
                pdf_header_space=row.get("pdf_header_space"),
                doctor_id=id_maps.get("user", {}).get(row.get("doctor_id")),
            )
            db.add(obj)
            db.flush()
            id_maps.setdefault("visit", {})[old_id] = obj.id

        for row in read_sqlite_rows(sqlite_conn, "prescription"):
            db.add(Prescription(
                visit_id=id_maps["visit"][row["visit_id"]],
                brand_medication_id=id_maps["brand_medication"][row["brand_medication_id"]],
                custom_drug_name=row.get("custom_drug_name"),
                custom_generic_name=row.get("custom_generic_name"),
                dosage=row.get("dosage"),
                dose_morning=row.get("dose_morning"),
                dose_afternoon=row.get("dose_afternoon"),
                dose_evening=row.get("dose_evening"),
                frequency=row.get("frequency"),
                timing=row.get("timing"),
                duration=row.get("duration"),
                instructions=row.get("instructions"),
                warnings=row.get("warnings"),
            ))

        db.commit()
        print("\nMigration complete.")
        for table in TABLES:
            pg_count = db.execute(text(f'SELECT COUNT(*) FROM "{table}"' if table == "user" else f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {pg_count} (sqlite: {counts_sqlite.get(table, 0)})")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
        sqlite_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite EMR data to PostgreSQL")
    parser.add_argument(
        "--sqlite",
        default=os.path.join(os.path.dirname(__file__), "..", "modern-EMR-main", "instance", "emr.db"),
    )
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL", "postgresql://emr:emr_secret@localhost:5432/endo_emr"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(os.path.abspath(args.sqlite), args.pg_url, args.dry_run)
