from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class PatientCreate(BaseModel):
    mrd_number: str | None = None
    name: str = Field(min_length=1, max_length=150)
    age: str = Field(min_length=1, max_length=10)
    sex: str = Field(min_length=1, max_length=10)
    contact: str | None = None
    address: str | None = None
    allergies: str | None = None
    problem_list: str | None = None
    temporary: bool = False
    doctor_id: int | None = None

    @field_validator("mrd_number", mode="before")
    @classmethod
    def normalize_mrd(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("contact")
    @classmethod
    def contact_ten_digits(cls, value):
        if value is None:
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return None
        if len(digits) != 10:
            raise ValueError("Mobile number must be 10 digits")
        return digits


class PatientUpdate(BaseModel):
    mrd_number: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    age: str | None = Field(default=None, min_length=1, max_length=10)
    sex: str | None = Field(default=None, min_length=1, max_length=10)
    contact: str | None = None
    address: str | None = None
    allergies: str | None = None
    problem_list: str | None = None

    @field_validator("mrd_number", mode="before")
    @classmethod
    def normalize_mrd(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("contact")
    @classmethod
    def contact_ten_digits(cls, value):
        if value is None:
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return None
        if len(digits) != 10:
            raise ValueError("Mobile number must be 10 digits")
        return digits


class PatientResponse(BaseModel):
    id: int
    mrd_number: str | None
    name: str
    age: str
    sex: str
    contact: str | None
    address: str | None
    allergies: str | None = None
    problem_list: str | None = None
    date_registered: datetime
    doctor_id: int | None
    clinic_id: int = 1
    registration_status: str = "active"

    model_config = {"from_attributes": True}


class VisitSummary(BaseModel):
    id: int
    visit_date: datetime
    visit_type: str
    status: str | None = None
    diagnosis: str | None
    chief_complaints: str | None

    model_config = {"from_attributes": True}


class PatientDetailResponse(PatientResponse):
    visits: list[VisitSummary] = []
