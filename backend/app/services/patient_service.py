"""Patient registration helpers."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Patient


def normalize_mrd(mrd: str | None) -> str | None:
    if mrd is None:
        return None
    cleaned = mrd.strip()
    return cleaned or None


def ensure_mrd_available(
    db: Session,
    mrd: str | None,
    *,
    exclude_patient_id: int | None = None,
) -> str | None:
    """Return normalized MRD or raise if already registered."""
    normalized = normalize_mrd(mrd)
    if not normalized:
        return None
    query = db.query(Patient).filter(Patient.mrd_number == normalized)
    if exclude_patient_id:
        query = query.filter(Patient.id != exclude_patient_id)
    existing = query.first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"MRD number '{normalized}' is already registered for {existing.name}",
        )
    return normalized
