from datetime import date, datetime

from pydantic import BaseModel, Field


class LabResultCreate(BaseModel):
    test_name: str = Field(min_length=1)
    value: str
    unit: str | None = None
    reference_range: str | None = None
    result_date: date | None = None
    visit_id: int | None = None
    notes: str | None = None


class LabResultResponse(LabResultCreate):
    id: int
    patient_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ImagingResultCreate(BaseModel):
    study_type: str = Field(min_length=1)
    findings: str | None = None
    report_date: date | None = None
    visit_id: int | None = None
    attachment_path: str | None = None


class ImagingResultResponse(ImagingResultCreate):
    id: int
    patient_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CgmReadingCreate(BaseModel):
    glucose_mg_dl: float = Field(gt=0)
    reading_time: datetime | None = None
    source: str | None = "manual"


class CgmReadingResponse(CgmReadingCreate):
    id: int
    patient_id: int

    model_config = {"from_attributes": True}


class AppointmentCreate(BaseModel):
    patient_id: int
    scheduled_at: datetime
    duration_minutes: int = 15
    status: str = "scheduled"
    notes: str | None = None


class AppointmentResponse(AppointmentCreate):
    id: int
    doctor_id: int
    patient_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BillCreate(BaseModel):
    visit_id: int
    description: str
    amount: float = Field(gt=0, description="Total amount in INR (inclusive of GST)")
    base_amount: float | None = Field(default=None, gt=0)
    gst_percent: float = Field(default=0, ge=0, le=28)
    gst_amount: float = Field(default=0, ge=0)
    procedure_code: str | None = Field(default=None, description="SAC/HSN code")
    payment_status: str = "pending"
    payment_method: str | None = None
    invoice_number: str | None = None


class BillUpdate(BaseModel):
    payment_status: str | None = None
    payment_method: str | None = None
    description: str | None = None


class BillResponse(BillCreate):
    id: int
    patient_id: int
    doctor_id: int
    patient_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CdsRecommendation(BaseModel):
    category: str
    severity: str
    source: str
    recommendation: str


class FollowUpItem(BaseModel):
    visit_id: int
    patient_id: int
    patient_name: str
    patient_mrd: str | None
    follow_up_date: date
    diagnosis: str | None
    days_overdue: int


class AnalyticsResponse(BaseModel):
    diagnosis_distribution: list[dict]
    visit_volume_by_month: list[dict]
    top_medications: list[dict]
    revenue_summary: dict
