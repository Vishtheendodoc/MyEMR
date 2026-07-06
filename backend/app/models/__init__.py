from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    visit: Mapped["Visit"] = relationship(back_populates="bills")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
