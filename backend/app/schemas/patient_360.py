"""Response models for the Patient 360 longitudinal chart."""

from pydantic import BaseModel, Field


class ParameterValue(BaseModel):
    date: str
    value_text: str
    value_numeric: float | None = None
    unit: str | None = None
    source: str


class ClinicalParameter(BaseModel):
    code: str
    name: str
    group: str
    unit: str | None = None
    reference_range: str | None = None
    note: str | None = None
    latest: ParameterValue | None = None
    previous: ParameterValue | None = None


class DiagnosisItem(BaseModel):
    text: str
    visit_id: int
    visit_date: str


class MedicationLine(BaseModel):
    visit_id: int
    visit_date: str
    drug_name: str
    generic_name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    timing: str | None = None
    duration: str | None = None
    dose_morning: str | None = None
    dose_afternoon: str | None = None
    dose_evening: str | None = None


class ReviewPrompt(BaseModel):
    code: str
    severity: str
    title: str
    explanation: str
    triggering: list[str] = Field(default_factory=list)


class PatientOverview(BaseModel):
    id: int
    name: str
    mrd_number: str | None = None
    age: str
    sex: str
    contact: str | None = None
    address: str | None = None
    date_of_birth: str | None = None
    date_registered: str
    allergies: str | None = None
    problem_list: str | None = None
    comorbidities: str | None = None
    visit_count: int
    active_diagnoses: list[DiagnosisItem] = Field(default_factory=list)
    current_medications: list[MedicationLine] = Field(default_factory=list)
    current_medications_visit_id: int | None = None
    current_medications_visit_date: str | None = None
    prompts: list[ReviewPrompt] = Field(default_factory=list)


class TrendPoint(BaseModel):
    date: str
    value: float


class TrendSeries(BaseModel):
    code: str
    name: str
    unit: str | None = None
    points: list[TrendPoint] = Field(default_factory=list)


class TrendGroup(BaseModel):
    id: str
    title: str
    series: list[TrendSeries] = Field(default_factory=list)


class CgmPoint(BaseModel):
    time: str
    glucose: float


class TimelineEvent(BaseModel):
    at: str
    kind: str
    title: str
    detail: str | None = None
    ref_type: str | None = None
    ref_id: int | None = None


class MedicationChange(BaseModel):
    change: str
    drug_name: str
    generic_name: str | None = None
    previous: str | None = None
    current: str | None = None


class NumericChange(BaseModel):
    code: str
    name: str
    unit: str | None = None
    previous_value: str | None = None
    current_value: str | None = None
    previous_date: str | None = None
    current_date: str | None = None
    direction: str


class VisitComparison(BaseModel):
    available: bool
    disclaimer: str
    previous_visit_id: int | None = None
    current_visit_id: int | None = None
    previous_visit_date: str | None = None
    current_visit_date: str | None = None
    previous_visit_status: str | None = None
    current_visit_status: str | None = None
    medication_note: str | None = None
    medication_changes: list[MedicationChange] = Field(default_factory=list)
    parameter_changes: list[NumericChange] = Field(default_factory=list)
    vital_changes: list[NumericChange] = Field(default_factory=list)
    diagnosis_previous: str | None = None
    diagnosis_current: str | None = None
    diagnoses_added: list[str] = Field(default_factory=list)
    diagnoses_removed: list[str] = Field(default_factory=list)
    investigations_previous: str | None = None
    investigations_current: str | None = None


class Patient360Response(BaseModel):
    generated_at: str
    display_timezone: str = "Asia/Kolkata"
    disclaimer: str
    overview: PatientOverview
    parameters: list[ClinicalParameter]
    trends: list[TrendGroup]
    cgm: list[CgmPoint]
    timeline: list[TimelineEvent]
    comparison: VisitComparison
