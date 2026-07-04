from datetime import datetime

from pydantic import BaseModel, Field


class PrescriptionCreate(BaseModel):
    brand_id: int | None = None
    custom_drug_name: str | None = None
    custom_generic_name: str | None = None
    dosage: str | None = None
    dose_morning: str | None = None
    dose_afternoon: str | None = None
    dose_evening: str | None = None
    frequency: str | None = None
    timing: str | None = None
    duration: str = Field(min_length=1)
    instructions: str | None = None


class PrescriptionResponse(BaseModel):
    id: int
    visit_id: int
    brand_medication_id: int
    custom_drug_name: str | None
    custom_generic_name: str | None
    dosage: str | None
    dose_morning: str | None
    dose_afternoon: str | None
    dose_evening: str | None
    frequency: str | None
    timing: str | None
    duration: str | None
    instructions: str | None
    warnings: str | None
    created_at: datetime
    drug_name: str | None = None
    generic_name: str | None = None
    formatted_dosage: str | None = None

    model_config = {"from_attributes": True}


class PrescriptionCreateResponse(BaseModel):
    success: bool
    prescription_id: int
    warnings: list[dict]
