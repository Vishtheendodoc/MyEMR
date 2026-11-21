from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(150))
    password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="doctor")
    qualifications: Mapped[str | None] = mapped_column(String(200))
    kmc_number: Mapped[str | None] = mapped_column(String(50))
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    acting_doctor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acting_clinic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    @property
    def doctor_name(self) -> str:
        return (self.display_name or self.username or "").strip()


class Patient(Base):
    __tablename__ = "patient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mrd_number: Mapped[str | None] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    age: Mapped[str] = mapped_column(String(10), nullable=False)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    date_registered: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    allergies: Mapped[str | None] = mapped_column(Text)
    problem_list: Mapped[str | None] = mapped_column(Text)
    registration_status: Mapped[str] = mapped_column(String(20), default="active")

    visits: Mapped[list["Visit"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    lab_results: Mapped[list["LabResult"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    imaging_results: Mapped[list["ImagingResult"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    cgm_readings: Mapped[list["CgmReading"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Visit(Base):
    __tablename__ = "visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    visit_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    visit_type: Mapped[str] = mapped_column(String(50), default="New Visit")
    chief_complaints: Mapped[str | None] = mapped_column(Text)
    height: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    mid_parental_height: Mapped[float | None] = mapped_column(Float)
    bp_systolic: Mapped[int | None] = mapped_column(Integer)
    bp_diastolic: Mapped[int | None] = mapped_column(Integer)
    pulse: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[int | None] = mapped_column(Integer)
    history: Mapped[str | None] = mapped_column(Text)
    examination: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    investigation: Mapped[str | None] = mapped_column(Text)
    ordered_investigations: Mapped[str | None] = mapped_column(Text)
    comorbidities: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    follow_up_notes: Mapped[str | None] = mapped_column(Text)
    specialty_template: Mapped[str | None] = mapped_column(String(50))
    specialty_data: Mapped[str | None] = mapped_column(Text)
    pdf_page_count: Mapped[int | None] = mapped_column(Integer)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    pdf_font_size: Mapped[int | None] = mapped_column(Integer, default=12)
    pdf_header_space: Mapped[int | None] = mapped_column(Integer, default=0)
    pdf_left_margin: Mapped[int | None] = mapped_column(Integer, default=12)
    pdf_hide_patient_info: Mapped[bool | None] = mapped_column(default=False)
    pdf_hide_header: Mapped[bool | None] = mapped_column(default=False)
    prevent_data: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    draft_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime)
    doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))

    patient: Mapped["Patient"] = relationship(back_populates="visits")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="visit", cascade="all, delete-orphan")
    bills: Mapped[list["Bill"]] = relationship(back_populates="visit", cascade="all, delete-orphan")


class GenericDrug(Base):
    __tablename__ = "generic_drug"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generic_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    drug_class: Mapped[str | None] = mapped_column(String(100))
    indication: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    brands: Mapped[list["BrandMedication"]] = relationship(back_populates="generic_drug", cascade="all, delete-orphan")
    interactions: Mapped[list["DrugComorbidityInteraction"]] = relationship(back_populates="generic_drug")


class BrandMedication(Base):
    __tablename__ = "brand_medication"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(200), nullable=False)
    generic_drug_id: Mapped[int] = mapped_column(Integer, ForeignKey("generic_drug.id"), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    strength: Mapped[str | None] = mapped_column(String(100))
    formulation: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    generic_drug: Mapped["GenericDrug"] = relationship(back_populates="brands")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="brand_medication")


class Comorbidity(Base):
    __tablename__ = "comorbidity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    drug_interactions: Mapped[list["DrugComorbidityInteraction"]] = relationship(back_populates="comorbidity")


class DiagnosisMaster(Base):
    __tablename__ = "diagnosis_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diagnosis_name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    icd_code: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DrugComorbidityInteraction(Base):
    __tablename__ = "drug_comorbidity_interaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generic_drug_id: Mapped[int] = mapped_column(Integer, ForeignKey("generic_drug.id"), nullable=False)
    comorbidity_id: Mapped[int] = mapped_column(Integer, ForeignKey("comorbidity.id"), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    generic_drug: Mapped["GenericDrug"] = relationship(back_populates="interactions")
    comorbidity: Mapped["Comorbidity"] = relationship(back_populates="drug_interactions")


class Prescription(Base):
    __tablename__ = "prescription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visit.id"), nullable=False)
    brand_medication_id: Mapped[int] = mapped_column(Integer, ForeignKey("brand_medication.id"), nullable=False)
    custom_drug_name: Mapped[str | None] = mapped_column(String(300))
    custom_generic_name: Mapped[str | None] = mapped_column(String(200))
    dosage: Mapped[str | None] = mapped_column(String(100))
    dose_morning: Mapped[str | None] = mapped_column(String(50))
    dose_afternoon: Mapped[str | None] = mapped_column(String(50))
    dose_evening: Mapped[str | None] = mapped_column(String(50))
    frequency: Mapped[str | None] = mapped_column(String(100))
    timing: Mapped[str | None] = mapped_column(String(100))
    duration: Mapped[str | None] = mapped_column(String(100))
    prescribed_quantity: Mapped[float | None] = mapped_column(Float)
    dispensed_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    dispense_status: Mapped[str] = mapped_column(String(20), default="pending")
    dispense_note: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    visit: Mapped["Visit"] = relationship(back_populates="prescriptions")
    brand_medication: Mapped["BrandMedication"] = relationship(back_populates="prescriptions")


class LabResult(Base):
    __tablename__ = "lab_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visit.id"))
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    reference_range: Mapped[str | None] = mapped_column(String(100))
    result_date: Mapped[date] = mapped_column(Date, default=date.today)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="lab_results")


class ImagingResult(Base):
    __tablename__ = "imaging_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visit.id"))
    study_type: Mapped[str] = mapped_column(String(200), nullable=False)
    findings: Mapped[str | None] = mapped_column(Text)
    report_date: Mapped[date] = mapped_column(Date, default=date.today)
    attachment_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="imaging_results")


class CgmReading(Base):
    __tablename__ = "cgm_reading"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    reading_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    glucose_mg_dl: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), default="manual")

    patient: Mapped["Patient"] = relationship(back_populates="cgm_readings")


class Appointment(Base):
    __tablename__ = "appointment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=15)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(20), default="in_clinic")
    token_number: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float)
    bp_systolic: Mapped[int | None] = mapped_column(Integer)
    bp_diastolic: Mapped[int | None] = mapped_column(Integer)
    pulse: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="appointments")


class Bill(Base):
    __tablename__ = "bill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visit.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    procedure_code: Mapped[str | None] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    base_amount: Mapped[float | None] = mapped_column(Float)
    gst_percent: Mapped[float] = mapped_column(Float, default=0.0)
    gst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    invoice_number: Mapped[str | None] = mapped_column(String(30))
    payment_status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_method: Mapped[str | None] = mapped_column(String(50))
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    line_items: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(30))
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)
    refund_reason: Mapped[str | None] = mapped_column(String(300))
    bill_type: Mapped[str | None] = mapped_column(String(30))
    cgst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    sgst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    igst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    place_of_supply: Mapped[str | None] = mapped_column(String(10))
    round_off: Mapped[float] = mapped_column(Float, default=0.0)
    advance_applied: Mapped[float] = mapped_column(Float, default=0.0)
    credit_note_number: Mapped[str | None] = mapped_column(String(30))
    debit_note_number: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    visit: Mapped["Visit"] = relationship(back_populates="bills")


class ClinicProfile(Base):
    __tablename__ = "clinic_profile"

    clinic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), default="Endo Clinic")
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    gstin: Mapped[str | None] = mapped_column(String(20))
    signatory: Mapped[str | None] = mapped_column(String(150))
    signature_data: Mapped[str | None] = mapped_column(Text)
    pharmacy_name: Mapped[str | None] = mapped_column(String(150))
    drug_licence: Mapped[str | None] = mapped_column(String(80))
    state_code: Mapped[str | None] = mapped_column(String(10))
    tax_mode: Mapped[str] = mapped_column(String(20), default="split")
    invoice_terms: Mapped[str | None] = mapped_column(Text)
    reminder_clinic_name: Mapped[str | None] = mapped_column(String(150))
    reminder_doctor_name: Mapped[str | None] = mapped_column(String(150))


class PriceItem(Base):
    __tablename__ = "price_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    kind: Mapped[str] = mapped_column(String(20), default="service")  # service | panel | favorite | medicine
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20))
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    gst_percent: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True)


class StockBatch(Base):
    __tablename__ = "stock_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    batch_no: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    reorder_level: Mapped[float] = mapped_column(Float, default=10.0)
    medicine_id: Mapped[int | None] = mapped_column(Integer)
    supplier_id: Mapped[int | None] = mapped_column(Integer)
    mfg_date: Mapped[date | None] = mapped_column(Date)
    purchase_rate: Mapped[float | None] = mapped_column(Float)
    mrp: Mapped[float | None] = mapped_column(Float)
    selling_price: Mapped[float | None] = mapped_column(Float)
    gst_percent: Mapped[float] = mapped_column(Float, default=0.0)
    location: Mapped[str | None] = mapped_column(String(80))
    stock_status: Mapped[str] = mapped_column(String(20), default="saleable")


class DayClose(Base):
    __tablename__ = "day_close"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    close_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cash_total: Mapped[float] = mapped_column(Float, default=0.0)
    upi_total: Mapped[float] = mapped_column(Float, default=0.0)
    card_total: Mapped[float] = mapped_column(Float, default=0.0)
    other_total: Mapped[float] = mapped_column(Float, default=0.0)
    billed_total: Mapped[float] = mapped_column(Float, default=0.0)
    collected_total: Mapped[float] = mapped_column(Float, default=0.0)
    opening_cash: Mapped[float] = mapped_column(Float, default=0.0)
    closing_cash: Mapped[float] = mapped_column(Float, default=0.0)
    closed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    closed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClinicalObservation(Base):
    """One measured or extracted clinical value.

    Rows copied from a lab, CGM reading, or visit are tied to that source record
    so the same result is not stored twice. Manual and imported rows have no source id.
    """

    __tablename__ = "clinical_observation"
    __table_args__ = (
        UniqueConstraint(
            "source_record_type",
            "source_record_id",
            "observation_code",
            name="uq_clinical_observation_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False, index=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visit.id"))
    observation_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    observation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    reference_range_low: Mapped[float | None] = mapped_column(Float)
    reference_range_high: Mapped[float | None] = mapped_column(Float)
    reference_range: Mapped[str | None] = mapped_column(String(100))
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_record_type: Mapped[str | None] = mapped_column(String(40))
    source_record_id: Mapped[int | None] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="recorded")
    verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MessageContact(Base):
    """A name and mobile saved for WhatsApp, apart from the patient register."""

    __tablename__ = "message_contact"
    __table_args__ = (UniqueConstraint("clinic_id", "phone", name="uq_message_contact_phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    list_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="saved", server_default="saved")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReminderLog(Base):
    __tablename__ = "reminder_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)  # appointment | follow_up
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), default="whatsapp")  # whatsapp | whatsapp_api | sms
    status: Mapped[str] = mapped_column(String(40), default="queued")  # queued | sent | opened | failed
    phone: Mapped[str | None] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClinicalRule(Base):
    """Versioned, editable threshold for one clinical review prompt."""

    __tablename__ = "clinical_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    guideline_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_review: Mapped[str] = mapped_column(Text, nullable=False)
    observation_code: Mapped[str | None] = mapped_column(String(80))
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="custom")
    threshold_low: Mapped[float | None] = mapped_column(Float)
    threshold_high: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClinicalAlert(Base):
    __tablename__ = "clinical_alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False, index=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    triggering_parameters: Mapped[str | None] = mapped_column(Text)
    previous_values: Mapped[str | None] = mapped_column(Text)
    recommended_review: Mapped[str] = mapped_column(Text, nullable=False)
    guideline_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    override_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime)
    acted_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))


class DrugPairInteraction(Base):
    __tablename__ = "drug_pair_interaction"
    __table_args__ = (
        UniqueConstraint("generic_a", "generic_b", name="uq_drug_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generic_a: Mapped[str] = mapped_column(String(200), nullable=False)
    generic_b: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)


class SubstitutionRequest(Base):
    """A requested brand change. Approval records the decision and does not rewrite the prescription."""

    __tablename__ = "substitution_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False, index=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescription.id"), nullable=False)
    current_label: Mapped[str] = mapped_column(String(300), nullable=False)
    requested_brand: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class RefreshSession(Base):
    __tablename__ = "refresh_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    replaced_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Supplier(Base):
    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(20))
    drug_licence: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MedicineItem(Base):
    """Pharmacy product. Stock is kept in the smallest unit (a tablet, ml, or piece)."""

    __tablename__ = "medicine_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    brand_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    generic_name: Mapped[str | None] = mapped_column(String(200))
    composition: Mapped[str | None] = mapped_column(String(300))
    strength: Mapped[str | None] = mapped_column(String(80))
    dosage_form: Mapped[str | None] = mapped_column(String(40))
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(80))
    schedule: Mapped[str | None] = mapped_column(String(20))
    hsn_code: Mapped[str | None] = mapped_column(String(20))
    gst_percent: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_price: Mapped[float | None] = mapped_column(Float)
    mrp: Mapped[float | None] = mapped_column(Float)
    selling_price: Mapped[float | None] = mapped_column(Float)
    barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    min_stock: Mapped[float] = mapped_column(Float, default=0.0)
    reorder_level: Mapped[float] = mapped_column(Float, default=10.0)
    base_unit: Mapped[str] = mapped_column(String(20), default="tablet")
    pack_size: Mapped[float] = mapped_column(Float, default=1.0)
    strip_size: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InventoryTxn(Base):
    __tablename__ = "inventory_txn"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    txn_type: Mapped[str] = mapped_column(String(40), nullable=False)
    medicine_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(Integer)
    batch_no: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    previous_qty: Mapped[float] = mapped_column(Float, default=0.0)
    new_qty: Mapped[float] = mapped_column(Float, default=0.0)
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseInvoice(Base):
    __tablename__ = "purchase_invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("supplier.id"), nullable=False)
    document_no: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_invoice_no: Mapped[str] = mapped_column(String(60), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    gst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseLine(Base):
    __tablename__ = "purchase_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_invoice.id"), nullable=False, index=True)
    medicine_id: Mapped[int | None] = mapped_column(Integer)
    medicine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="tablet")
    free_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    base_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    purchase_rate: Mapped[float] = mapped_column(Float, default=0.0)
    mrp: Mapped[float | None] = mapped_column(Float)
    selling_price: Mapped[float | None] = mapped_column(Float)
    gst_percent: Mapped[float] = mapped_column(Float, default=0.0)
    line_total: Mapped[float] = mapped_column(Float, default=0.0)
    batch_id: Mapped[int | None] = mapped_column(Integer)
    returned_base: Mapped[float] = mapped_column(Float, default=0.0)


class BillPayment(Base):
    __tablename__ = "bill_payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(Integer, ForeignKey("bill.id"), nullable=False, index=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False, default="Cash")
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="collection")
    note: Mapped[str | None] = mapped_column(String(200))
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PatientAdvance(Base):
    """Money taken before a bill. Applying it later does not count the cash a second time."""

    __tablename__ = "patient_advance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False, default="Cash")
    note: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaxNote(Base):
    """A credit note or debit note with its own financial-year number."""

    __tablename__ = "tax_note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    bill_id: Mapped[int] = mapped_column(Integer, ForeignKey("bill.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    document_no: Mapped[str] = mapped_column(String(30), nullable=False)
    taxable: Mapped[float] = mapped_column(Float, default=0.0)
    gst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SalesReturn(Base):
    __tablename__ = "sales_return"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    bill_id: Mapped[int] = mapped_column(Integer, ForeignKey("bill.id"), nullable=False)
    document_no: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default="saleable")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SalesReturnLine(Base):
    __tablename__ = "sales_return_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_return_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales_return.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)


class PurchaseReturn(Base):
    __tablename__ = "purchase_return"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    purchase_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_invoice.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("supplier.id"), nullable=False)
    document_no: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_credit_no: Mapped[str | None] = mapped_column(String(60))
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseReturnLine(Base):
    __tablename__ = "purchase_return_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_return_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_return.id"), nullable=False)
    purchase_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_line.id"), nullable=False)
    medicine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
