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
    channel: str = "in_clinic"


class AppointmentResponse(AppointmentCreate):
    id: int
    doctor_id: int
    patient_name: str | None = None
    patient_contact: str | None = None
    patient_mrd: str | None = None
    registration_status: str | None = None
    token_number: int | None = None
    height: float | None = None
    weight: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    pulse: int | None = None
    temperature: float | None = None
    spo2: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    status: str | None = None
    notes: str | None = None
    height: float | None = None
    weight: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    pulse: int | None = None
    temperature: float | None = None
    spo2: int | None = None


class BillLine(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    procedure_code: str | None = None
    quantity: float = Field(default=1, gt=0, le=999)
    rate: float | None = Field(default=None, gt=0)
    base_amount: float | None = Field(default=None, gt=0)
    gst_percent: float = Field(default=0, ge=0, le=40)
    gst_amount: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=200)
    batch_id: int | None = None


class PaymentPart(BaseModel):
    method: str = "Cash"
    amount: float = Field(gt=0)


class BillCreate(BaseModel):
    visit_id: int
    description: str = ""
    amount: float | None = Field(default=None, gt=0, description="Total amount in INR after discount")
    base_amount: float | None = Field(default=None, gt=0)
    gst_percent: float = Field(default=0, ge=0, le=28)
    gst_amount: float = Field(default=0, ge=0)
    procedure_code: str | None = Field(default=None, description="SAC/HSN code")
    payment_status: str = "pending"
    payment_method: str | None = None
    invoice_number: str | None = None
    discount_amount: float = Field(default=0, ge=0)
    amount_paid: float = Field(default=0, ge=0)
    line_items: list[BillLine] | None = None
    category: str | None = None
    append_to_visit: bool = False
    refund_amount: float = Field(default=0, ge=0)
    refund_reason: str | None = None
    payments: list[PaymentPart] | None = None
    place_of_supply: str | None = None
    advance_applied: float = Field(default=0, ge=0)


class DebitNoteIn(BaseModel):
    amount: float = Field(gt=0)
    gst_percent: float = Field(default=0, ge=0, le=40)
    reason: str = Field(min_length=3, max_length=300)


class BillUpdate(BaseModel):
    payment_status: str | None = None
    payment_method: str | None = None
    description: str | None = None
    amount_paid: float | None = Field(default=None, ge=0)
    refund_amount: float | None = Field(default=None, ge=0)
    refund_reason: str | None = None
    payments: list[PaymentPart] | None = None


class BillPaymentOut(BaseModel):
    amount: float
    method: str
    kind: str = "collection"
    note: str | None = None
    created_at: datetime | None = None


class BillResponse(BillCreate):
    id: int
    patient_id: int
    doctor_id: int
    patient_name: str | None = None
    patient_mrd: str | None = None
    patient_age: str | None = None
    patient_sex: str | None = None
    bill_type: str | None = None
    cgst_amount: float = 0
    sgst_amount: float = 0
    igst_amount: float = 0
    place_of_supply: str | None = None
    round_off: float = 0
    advance_applied: float = 0
    credit_note_number: str | None = None
    debit_note_number: str | None = None
    created_at: datetime
    receipts: list[BillPaymentOut] = []

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
    patient_contact: str | None = None
    follow_up_date: date
    follow_up_notes: str | None = None
    diagnosis: str | None
    days_overdue: int
    days_until: int = 0
    bucket: str = "overdue"


class ReminderSendRequest(BaseModel):
    source_type: str  # appointment | follow_up
    source_id: int
    auto_send: bool = False
    message: str | None = None


class AnalyticsResponse(BaseModel):
    diagnosis_distribution: list[dict]
    visit_volume_by_month: list[dict]
    top_medications: list[dict]
    revenue_summary: dict
