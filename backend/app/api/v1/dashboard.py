from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import BrandMedication, GenericDrug, Patient, User, Visit
from app.schemas.dashboard import DashboardResponse, DashboardStats, RecentVisitItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recent = (
        db.query(Visit)
        .join(Patient)
        .options(joinedload(Visit.patient))
        .filter(Visit.doctor_id == user.id)
        .order_by(Visit.visit_date.desc())
        .limit(10)
        .all()
    )
    stats = DashboardStats(
        total_patients=db.query(Patient).filter_by(doctor_id=user.id).count(),
        total_visits=db.query(Visit).filter_by(doctor_id=user.id).count(),
        total_drugs=db.query(GenericDrug).count(),
        total_brands=db.query(BrandMedication).count(),
    )
    recent_items = [
        RecentVisitItem(
            id=v.id,
            visit_date=v.visit_date,
            visit_type=v.visit_type,
            diagnosis=v.diagnosis,
            chief_complaints=v.chief_complaints,
            patient_id=v.patient_id,
            patient_name=v.patient.name,
            patient_mrd=v.patient.mrd_number,
        )
        for v in recent
    ]
    return DashboardResponse(stats=stats, recent_visits=recent_items)
