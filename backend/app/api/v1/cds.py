from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Visit
from app.schemas.extended import CdsRecommendation
from app.services.ai.cds_engine import get_cds_recommendations

router = APIRouter(tags=["cds"])


@router.get("/visits/{visit_id}/cds", response_model=list[CdsRecommendation])
def visit_cds(visit_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.patient), joinedload(Visit.prescriptions))
        .filter_by(id=visit_id)
        .first()
    )
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    return get_cds_recommendations(db, visit)
