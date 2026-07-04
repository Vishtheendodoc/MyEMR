from datetime import datetime

from pydantic import BaseModel


class BrandResponse(BaseModel):
    id: int
    brand_name: str
    display_label: str
    manufacturer: str | None
    strength: str | None
    formulation: str | None
    price: float | None
    is_insulin: bool
    suggested_dosage: str | None


class GenericSearchResult(BaseModel):
    type: str
    id: int
    generic_name: str
    drug_class: str | None = None
    indication: str | None = None
    brand_id: int | None = None
    brand_name: str | None = None
    display_label: str | None = None
    is_insulin: bool | None = None
    strength: str | None = None
    formulation: str | None = None
    suggested_dosage: str | None = None


class GenericDrugResponse(BaseModel):
    id: int
    generic_name: str
    drug_class: str | None
    indication: str | None
    created_at: datetime
    brands: list[BrandResponse] = []

    model_config = {"from_attributes": True}


class MedicationUploadResponse(BaseModel):
    generic_count: int
    brand_count: int
    removed_count: int


class MedicationStatsResponse(BaseModel):
    total_listed: int
    total_custom: int
    total_prescriptions: int
    brands_prescribed: int
    custom_drugs_prescribed: int
    listed_rows: list[dict]
    custom_rows: list[dict]
