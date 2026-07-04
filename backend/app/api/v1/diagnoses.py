import os

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import DiagnosisMaster, User
from app.schemas.diagnosis import DiagnosisResponse, DiagnosisUploadResponse
from app.services.medication_service import process_diagnosis_rows

router = APIRouter(prefix="/diagnoses", tags=["diagnoses"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=list[DiagnosisResponse])
def list_diagnoses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(DiagnosisMaster)
        .order_by(DiagnosisMaster.category, DiagnosisMaster.diagnosis_name)
        .all()
    )


@router.post("/upload", response_model=DiagnosisUploadResponse)
async def upload_diagnoses(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    filepath = os.path.join(UPLOAD_DIR, file.filename or "diagnoses.csv")
    with open(filepath, "wb") as f:
        f.write(content)
    try:
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        if "diagnosis_name" not in df.columns:
            raise ValueError("Missing required column: diagnosis_name")
        count = process_diagnosis_rows(db, df.to_dict("records"))
        return DiagnosisUploadResponse(count=count)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
