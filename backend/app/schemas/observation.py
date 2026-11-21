from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, field_validator


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class ObservationCreate(BaseModel):
    observation_code: str = Field(min_length=1, max_length=80)
    observation_name: str = Field(min_length=1, max_length=200)
    value_text: str = Field(min_length=1, max_length=100)
    value_numeric: float | None = None
    unit: str | None = Field(default=None, max_length=50)
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    reference_range: str | None = Field(default=None, max_length=100)
    observed_at: datetime
    source: str = Field(pattern="^(manual|imported|laboratory_report)$")
    visit_id: int | None = None

    @field_validator("observation_code")
    @classmethod
    def code_shape(cls, value: str) -> str:
        cleaned = value.strip().lower().replace(" ", "_")
        if not cleaned.replace("_", "").replace(".", "").isalnum():
            raise ValueError("Use letters, numbers, dots, or underscores for the code")
        return cleaned[:80]

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_observed_at(cls, value):
        if isinstance(value, datetime):
            return _as_naive_utc(value)
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        text = str(value).strip()
        if len(text) == 10:
            parsed = date.fromisoformat(text)
            return datetime(parsed.year, parsed.month, parsed.day)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _as_naive_utc(parsed)


class ObservationResponse(BaseModel):
    id: int
    patient_id: int
    visit_id: int | None
    observation_code: str
    observation_name: str
    value_numeric: float | None
    value_text: str
    unit: str | None
    reference_range_low: float | None
    reference_range_high: float | None
    reference_range: str | None
    observed_at: datetime
    source: str
    source_record_type: str | None
    source_record_id: int | None
    verification_status: str
    verified_by: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
