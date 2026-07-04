from datetime import datetime

from pydantic import BaseModel


class DiagnosisResponse(BaseModel):
    id: int
    diagnosis_name: str
    category: str | None
    icd_code: str | None
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DiagnosisUploadResponse(BaseModel):
    count: int
