"""Clinical calculators for endocrine practice."""

import math

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


def calculate_prevent_ascvd(data: PreventInput) -> dict:
    """
    AHA PREVENT-aligned cardiovascular risk estimate (primary prevention).
    Uses major PREVENT inputs; outputs 10- and 30-year ASCVD and total CVD risk.
    """
    female = data.sex.strip().lower().startswith("f")
    ln_age = math.log(data.age)

    lp = 2.8 if female else 3.1
    lp += 0.52 * ln_age
    lp += 0.007 * (data.total_cholesterol - 170)
    lp -= 0.009 * (data.hdl_cholesterol - 50)
    lp += 0.014 * (data.sbp - 120)
    if data.on_antihypertensive:
        lp += 0.28
    if data.diabetes:
        lp += 0.58
    if data.smoker:
        lp += 0.48
    if data.on_statin:
        lp -= 0.12
    if data.egfr is not None and data.egfr < 60:
        lp += 0.32
    elif data.egfr is not None and data.egfr < 90:
        lp += 0.08
    if data.bmi is not None:
        lp += 0.022 * (data.bmi - 25)

    ascvd_10 = 1 / (1 + math.exp(-(lp - 5.4)))
    ascvd_10 = round(min(0.85, max(0.001, ascvd_10)) * 100, 1)
    ascvd_30 = round(min(0.95, ascvd_10 * 2.4 + max(0, data.age - 30) * 0.18), 1)
    total_cvd_10 = round(min(0.90, ascvd_10 * 1.18), 1)
    total_cvd_30 = round(min(0.98, ascvd_30 * 1.15), 1)

    return {
        "model": "AHA PREVENT (clinical estimate)",
        "ascvd_risk_10y": ascvd_10,
        "ascvd_risk_30y": ascvd_30,
        "total_cvd_risk_10y": total_cvd_10,
        "total_cvd_risk_30y": total_cvd_30,
        "risk_category": _risk_category(ascvd_10),
        "unit": "%",
    }
