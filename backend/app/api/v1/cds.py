from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import require_role
from app.models import Visit
from app.schemas.extended import CdsRecommendation
from app.services.ai.cds_engine import get_cds_recommendations
from app.services.clinic_scope import ensure_patient_access

router = APIRouter(tags=["cds"])


@router.get("/visits/{visit_id}/cds", response_model=list[CdsRecommendation])
def visit_cds(visit_id: int, user=Depends(require_role()), db: Session = Depends(get_db)):
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.patient), joinedload(Visit.prescriptions))
        .filter_by(id=visit_id)
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    ensure_patient_access(db, visit.patient_id, user)
    return get_cds_recommendations(db, visit)
