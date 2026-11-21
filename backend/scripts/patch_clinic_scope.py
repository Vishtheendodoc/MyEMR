"""One-off helper to patch API modules for clinic scoping. Safe to re-run."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "app" / "api" / "v1"


def patch_visits():
    p = ROOT / "visits.py"
    text = p.read_text(encoding="utf-8")
    if "clinic_scope" not in text:
        text = text.replace(
            "from app.models import BrandMedication, Patient, Prescription, User, Visit",
            "from app.models import BrandMedication, Patient, Prescription, User, Visit\n"
            "from app.services.clinic_scope import ensure_patient_access, ensure_visit_access, owning_doctor_id",
        )
    text = text.replace(
        "    patient = db.get(Patient, patient_id)\n"
        "    if not patient or patient.doctor_id != user.id:\n"
        '        raise HTTPException(status_code=404, detail="Patient not found")\n'
        "\n"
        "    bmi = None\n"
        "    if data.height and data.weight:\n"
        "        height_m = data.height / 100\n"
        "        bmi = round(data.weight / (height_m ** 2), 2)\n"
        "\n"
        "    visit = Visit(\n"
        "        patient_id=patient_id,\n"
        "        doctor_id=user.id,",
        "    patient = ensure_patient_access(db, patient_id, user)\n"
        "\n"
        "    bmi = None\n"
        "    if data.height and data.weight:\n"
        "        height_m = data.height / 100\n"
        "        bmi = round(data.weight / (height_m ** 2), 2)\n"
        "\n"
        "    visit = Visit(\n"
        "        patient_id=patient_id,\n"
        "        doctor_id=owning_doctor_id(db, user),",
    )
    text = text.replace(
        "    create_appointment_from_follow_up(db, visit, user.id)\n"
        "\n"
        "    db.commit()\n"
        "    db.refresh(visit)\n"
        "    visit.patient = patient\n"
        "    return _visit_response(visit)",
        "    create_appointment_from_follow_up(db, visit, owning_doctor_id(db, user))\n"
        "\n"
        "    db.commit()\n"
        "    db.refresh(visit)\n"
        "    visit.patient = patient\n"
        "    return _visit_response(visit)",
    )
    text = text.replace(
        "    visit = db.query(Visit).options(joinedload(Visit.patient)).filter_by(id=visit_id).first()\n"
        "    if not visit or visit.doctor_id != user.id:\n"
        '        raise HTTPException(status_code=404, detail="Visit not found")',
        "    visit = db.query(Visit).options(joinedload(Visit.patient)).filter_by(id=visit_id).first()\n"
        "    if not visit:\n"
        '        raise HTTPException(status_code=404, detail="Visit not found")\n'
        "    ensure_patient_access(db, visit.patient_id, user)",
    )
    text = re.sub(
        r"visit = db\.get\(Visit, visit_id\)\n"
        r"    if not visit or visit\.doctor_id != user\.id:\n"
        r'        raise HTTPException\(status_code=404, detail="Visit not found"\)',
        "visit = ensure_visit_access(db, visit_id, user)",
        text,
    )
    text = re.sub(
        r"visit = db\.get\(Visit, visit_id\)\n"
        r"    if not visit or visit\.doctor_id != user\.id:\n"
        r'        raise HTTPException\(status_code=403, detail="Unauthorized"\)',
        "visit = ensure_visit_access(db, visit_id, user)",
        text,
    )
    # follow-up create uses user.id — keep owning doctor
    text = text.replace(
        "create_appointment_from_follow_up(db, visit, user.id)",
        "create_appointment_from_follow_up(db, visit, owning_doctor_id(db, user))",
    )
    p.write_text(text, encoding="utf-8")
    print("patched visits.py")


def patch_simple(path: str, replacements: list[tuple[str, str]], import_line: str | None = None, import_add: str | None = None):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if import_line and import_add and import_add not in text:
        text = text.replace(import_line, import_line + "\n" + import_add)
    for a, b in replacements:
        text = text.replace(a, b)
    p.write_text(text, encoding="utf-8")
    print(f"patched {path}")


if __name__ == "__main__":
    patch_visits()
    patch_simple(
        "labs.py",
        [
            (
                "def _check_patient(db: Session, patient_id: int, user: User) -> Patient:\n"
                "    patient = db.get(Patient, patient_id)\n"
                "    if not patient or patient.doctor_id != user.id:\n"
                '        raise HTTPException(status_code=404, detail="Patient not found")\n'
                "    return patient",
                "def _check_patient(db: Session, patient_id: int, user: User) -> Patient:\n"
                "    return ensure_patient_access(db, patient_id, user)",
            ),
            (
                ".filter(Visit.doctor_id == user.id, Visit.follow_up_date.isnot(None))",
                ".join(Patient, Visit.patient_id == Patient.id)\n"
                "        .filter(Patient.clinic_id == clinic_id_of(user), Visit.follow_up_date.isnot(None))",
            ),
        ],
        "from app.models import ImagingResult, LabResult, Patient, User",
        "from app.services.clinic_scope import clinic_id_of, ensure_patient_access",
    )
    patch_simple(
        "specialty.py",
        [
            (
                "def _patient(db: Session, pid: int, user):\n"
                "    p = db.get(Patient, pid)\n"
                "    if not p or p.doctor_id != user.id:\n"
                '        raise HTTPException(status_code=404, detail="Patient not found")\n'
                "    return p",
                "def _patient(db: Session, pid: int, user):\n"
                "    return ensure_patient_access(db, pid, user)",
            ),
        ],
        "from app.models import CgmReading, Patient, Visit",
        "from app.services.clinic_scope import ensure_patient_access",
    )
    patch_simple(
        "cds.py",
        [
            (
                "    if not visit or visit.doctor_id != user.id:",
                "    if not visit:\n"
                '        raise HTTPException(status_code=404, detail="Visit not found")\n'
                "    ensure_patient_access(db, visit.patient_id, user)\n"
                "    if False:",
            ),
        ],
    )
