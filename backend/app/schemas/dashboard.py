from datetime import datetime

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


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_visits: list[RecentVisitItem]
