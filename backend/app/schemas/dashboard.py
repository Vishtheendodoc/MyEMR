from datetime import datetime, time, timedelta

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_patients: int
    total_visits: int
    total_drugs: int
    total_brands: int


class RecentVisitItem(BaseModel):
    id: int
    visit_date: datetime
    visit_type: str
    diagnosis: str | None
    chief_complaints: str | None
    patient_id: int
    patient_name: str
    patient_mrd: str | None

    model_config = {"from_attributes": True}


class TodayConsult(BaseModel):
    appointment_id: int | None = None
    visit_id: int | None = None
    patient_id: int
    patient_name: str
    patient_mrd: str | None = None
    patient_age: str | None = None
    patient_sex: str | None = None
    scheduled_at: datetime | None = None
    token_number: int | None = None
    status: str
    channel: str
    kind: str
    complaint: str | None = None


class TodayBoard(BaseModel):
    date: str
    consultations: list[TodayConsult]
    booked: int = 0
    waiting: int = 0
    in_consult: int = 0
    done: int = 0
    new: int = 0
    revisit: int = 0
    walk_in: int = 0
    online: int = 0


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_visits: list[RecentVisitItem]
    today: TodayBoard
