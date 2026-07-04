from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VisitCreate(BaseModel):
    visit_type: str = "New Visit"
    chief_complaints: str | None = None
    height: float | None = None
    weight: float | None = None
    mid_parental_height: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    pulse: int | None = None
    temperature: float | None = None
    spo2: int | None = None
    history: str | None = None
    examination: str | None = None
    diagnosis: str | None = None
    investigation: str | None = None
    comorbidities: str | None = None
    follow_up_date: date | None = None
    follow_up_notes: str | None = None
    specialty_template: str | None = None
    specialty_data: dict[str, Any] | None = None
    prevent_data: dict[str, Any] | None = None

    @field_validator("follow_up_date")
    @classmethod
    def follow_up_must_be_future(cls, value: date | None) -> date | None:
        if value is not None and value <= date.today():
            raise ValueError("Follow-up date must be a future date")
        return value


class VisitUpdate(VisitCreate):
    pass


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    visit_date: datetime
    visit_type: str
    chief_complaints: str | None
    height: float | None
    weight: float | None
    bmi: float | None
    mid_parental_height: float | None = None
    bp_systolic: int | None
    bp_diastolic: int | None
    pulse: int | None
    temperature: float | None
    spo2: int | None
    history: str | None
    examination: str | None
    diagnosis: str | None
    investigation: str | None
    comorbidities: str | None
    follow_up_date: date | None
    follow_up_notes: str | None
    specialty_template: str | None = None
    specialty_data: str | None = None
    pdf_page_count: int | None
    pdf_font_size: int | None
    pdf_header_space: int | None
    pdf_left_margin: int | None = None
    pdf_hide_patient_info: bool | None = None
    pdf_hide_header: bool | None = None
    status: str = "draft"
    draft_updated_at: datetime | None = None
    finalized_at: datetime | None = None
    doctor_id: int | None
    patient_name: str | None = None
    patient_mrd: str | None = None

    model_config = {"from_attributes": True}


class InteractionWarning(BaseModel):
    drug: str
    comorbidity: str
    type: str
    severity: str | None
    recommendation: str | None


class VisitDetailResponse(VisitResponse):
    prescriptions: list["PrescriptionResponse"] = []
    warnings: list[InteractionWarning] = []
    specialty_fields: list[dict] = []
    investigations_text: str | None = None
    prevent_data: dict[str, Any] | None = None
    can_finalize: bool = False


from app.schemas.prescription import PrescriptionResponse  # noqa: E402

VisitDetailResponse.model_rebuild()
