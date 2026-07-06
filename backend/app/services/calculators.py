"""Clinical calculators for endocrine practice."""

import pyprevent
from pydantic import BaseModel, Field


class EgfrInput(BaseModel):
    creatinine_mg_dl: float = Field(gt=0)
    age: int = Field(ge=1, le=120)
    sex: str
    is_african_american: bool = False


class InstructionText(BaseModel):
    text: str = Field(min_length=1)


class HomaIrInput(BaseModel):
    fasting_glucose_mg_dl: float = Field(gt=0)
    fasting_insulin_uIU_ml: float = Field(gt=0)


class CorrectedCalciumInput(BaseModel):
    calcium_mg_dl: float = Field(gt=0)
    albumin_g_dl: float = Field(gt=0)


class SteroidConversionInput(BaseModel):
    dose_mg: float = Field(gt=0)
    from_steroid: str
    to_steroid: str


class PreventInput(BaseModel):
    age: int = Field(ge=30, le=79)
    sex: str
    total_cholesterol: float = Field(gt=0, description="mg/dL")
    hdl_cholesterol: float = Field(gt=0, description="mg/dL")
    sbp: float = Field(gt=0, description="mmHg")
    on_antihypertensive: bool = False
    diabetes: bool = False
    smoker: bool = False
    egfr: float | None = Field(default=None, gt=0)
    bmi: float | None = Field(default=None, gt=0)
    on_statin: bool = False


STEROID_POTENCY = {
    "hydrocortisone": 1.0,
    "cortisone": 0.8,
    "prednisolone": 4.0,
    "prednisone": 4.0,
    "methylprednisolone": 5.0,
    "dexamethasone": 25.0,
    "betamethasone": 25.0,
}


def calculate_egfr(data: EgfrInput) -> dict:
    scr = data.creatinine_mg_dl
    age = data.age
    sex = data.sex.strip().lower()
    if sex.startswith("f"):
        k, alpha = 0.7, -0.329
    else:
        k, alpha = 0.9, -0.411
    egfr = 141 * (min(scr / k, 1) ** alpha) * (max(scr / k, 1) ** -1.209) * (0.993 ** age)
    if data.is_african_american:
        egfr *= 1.159
    if sex.startswith("f"):
        egfr *= 1.018
    egfr = round(egfr, 1)
    stage = "G1" if egfr >= 90 else "G2" if egfr >= 60 else "G3a" if egfr >= 45 else "G3b" if egfr >= 30 else "G4" if egfr >= 15 else "G5"
    return {"egfr": egfr, "ckd_stage": stage, "unit": "mL/min/1.73m²"}


def calculate_homa_ir(data: HomaIrInput) -> dict:
    val = round((data.fasting_glucose_mg_dl * data.fasting_insulin_uIU_ml) / 405, 2)
    interpretation = "Normal" if val < 1.5 else "Early insulin resistance" if val < 2.5 else "Significant insulin resistance"
    return {"homa_ir": val, "interpretation": interpretation}


def calculate_corrected_calcium(data: CorrectedCalciumInput) -> dict:
    corrected = round(data.calcium_mg_dl + 0.8 * (4.0 - data.albumin_g_dl), 2)
    return {"corrected_calcium_mg_dl": corrected, "formula": "Payne formula (albumin 4 g/dL reference)"}


def convert_steroid(data: SteroidConversionInput) -> dict:
    f = data.from_steroid.strip().lower()
    t = data.to_steroid.strip().lower()
    if f not in STEROID_POTENCY or t not in STEROID_POTENCY:
        raise ValueError(f"Unknown steroid. Supported: {', '.join(STEROID_POTENCY)}")
    equivalent = round(data.dose_mg * STEROID_POTENCY[f] / STEROID_POTENCY[t], 2)
    return {"equivalent_dose_mg": equivalent, "from": f, "to": t}


def _risk_category(risk_pct: float) -> str:
    if risk_pct < 5:
        return "Low"
    if risk_pct < 7.5:
        return "Borderline"
    if risk_pct < 20:
        return "Intermediate"
    return "High"


def _normalize_prevent_sex(sex: str) -> str:
    return "female" if sex.strip().lower().startswith("f") else "male"


def _clamp_prevent_value(value: float, lo: float, hi: float, label: str, notes: list[str]) -> float:
    if value < lo:
        notes.append(f"{label} clamped from {value} to {lo}")
        return lo
    if value > hi:
        notes.append(f"{label} clamped from {value} to {hi}")
        return hi
    return value


def _prepare_prevent_params(data: PreventInput) -> tuple[dict, list[str]]:
    notes: list[str] = []

    bmi = data.bmi if data.bmi is not None else 25.0
    if data.bmi is None:
        notes.append("BMI imputed as 25 (not provided)")

    egfr = data.egfr if data.egfr is not None else 90.0
    if data.egfr is None:
        notes.append("eGFR imputed as 90 (not provided)")

    params = {
        "sex": _normalize_prevent_sex(data.sex),
        "age": float(data.age),
        "total_cholesterol": _clamp_prevent_value(data.total_cholesterol, 130, 320, "Total cholesterol", notes),
        "hdl_cholesterol": _clamp_prevent_value(data.hdl_cholesterol, 20, 100, "HDL cholesterol", notes),
        "systolic_bp": _clamp_prevent_value(data.sbp, 90, 200, "Systolic BP", notes),
        "has_diabetes": data.diabetes,
        "current_smoker": data.smoker,
        "bmi": _clamp_prevent_value(bmi, 18.5, 39.9, "BMI", notes),
        "egfr": _clamp_prevent_value(egfr, 15, 140, "eGFR", notes),
        "on_htn_meds": data.on_antihypertensive,
        "on_cholesterol_meds": data.on_statin,
    }
    return params, notes


def calculate_prevent_ascvd(data: PreventInput) -> dict:
    """
    AHA PREVENT Base Model (Khan et al., Circulation 2024) via official equations.
    Outputs 10- and 30-year ASCVD and total CVD risk percentages.
    """
    params, notes = _prepare_prevent_params(data)

    ascvd_10 = round(pyprevent.calculate_10_yr_ascvd_risk(**params), 1)
    total_cvd_10 = round(pyprevent.calculate_10_yr_cvd_risk(**params), 1)

    ascvd_30 = None
    total_cvd_30 = None
    if data.age <= 59:
        ascvd_30 = round(pyprevent.calculate_30_yr_ascvd_risk(**params), 1)
        total_cvd_30 = round(pyprevent.calculate_30_yr_cvd_risk(**params), 1)
    else:
        notes.append("30-year risk not reported for age >59 per PREVENT model")

    result = {
        "model": "AHA PREVENT Base Model",
        "ascvd_risk_10y": ascvd_10,
        "ascvd_risk_30y": ascvd_30,
        "total_cvd_risk_10y": total_cvd_10,
        "total_cvd_risk_30y": total_cvd_30,
        "risk_category": _risk_category(ascvd_10),
        "unit": "%",
    }
    if notes:
        result["notes"] = notes
    return result


from app.services.pcos_scoring import (  # noqa: E402
    FerrimanGallweyInput,
    calculate_ferriman_gallwey,
    interpret_ludwig,
)
