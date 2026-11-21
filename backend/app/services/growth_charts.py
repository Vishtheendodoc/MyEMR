"""CDC growth reference curves (0–24 months and 2–20 years) with SD / Z-score."""

from __future__ import annotations

import math
import re
from datetime import date, datetime

from app.services.clinic_time import clinic_day

# (age_months, median_cm, sd_cm) — CDC length/stature reference (approx.)
BOYS_INFANT: list[tuple[int, float, float]] = [
    (0, 49.9, 1.9), (1, 54.7, 2.0), (2, 58.4, 2.1), (3, 61.4, 2.1), (4, 64.0, 2.1),
    (5, 66.2, 2.1), (6, 67.6, 2.1), (7, 69.2, 2.1), (8, 70.6, 2.1), (9, 72.0, 2.1),
    (10, 73.3, 2.1), (11, 74.5, 2.1), (12, 75.7, 2.1), (15, 79.1, 2.2), (18, 82.3, 2.2),
    (21, 85.1, 2.2), (24, 87.8, 2.2),
]
GIRLS_INFANT: list[tuple[int, float, float]] = [
    (0, 49.1, 1.8), (1, 53.7, 1.9), (2, 57.1, 2.0), (3, 59.8, 2.0), (4, 62.1, 2.0),
    (5, 64.0, 2.0), (6, 65.7, 2.0), (7, 67.3, 2.0), (8, 68.7, 2.0), (9, 70.1, 2.0),
    (10, 71.5, 2.0), (11, 72.8, 2.0), (12, 74.0, 2.0), (15, 77.5, 2.1), (18, 80.7, 2.1),
    (21, 83.7, 2.1), (24, 86.4, 2.1),
]

BOYS_CHILD: list[tuple[int, float, float]] = [
    (2, 87.1, 3.2), (3, 96.1, 3.5), (4, 103.3, 3.7), (5, 110.0, 3.9), (6, 116.0, 4.1),
    (7, 121.7, 4.3), (8, 127.2, 4.5), (9, 132.6, 4.7), (10, 137.8, 4.9), (11, 143.5, 5.1),
    (12, 149.0, 5.5), (13, 156.2, 6.0), (14, 164.5, 6.2), (15, 170.8, 6.0), (16, 174.6, 5.8),
    (17, 176.0, 5.6), (18, 176.5, 5.5), (19, 176.8, 5.4), (20, 177.0, 5.3),
]
GIRLS_CHILD: list[tuple[int, float, float]] = [
    (2, 86.0, 3.1), (3, 95.1, 3.4), (4, 101.8, 3.6), (5, 108.4, 3.8), (6, 114.6, 4.0),
    (7, 120.6, 4.2), (8, 126.4, 4.4), (9, 132.2, 4.6), (10, 138.3, 4.8), (11, 144.0, 5.0),
    (12, 149.8, 5.3), (13, 156.7, 5.5), (14, 159.7, 5.4), (15, 161.8, 5.2), (16, 162.5, 5.1),
    (17, 162.5, 5.0), (18, 162.5, 5.0), (19, 162.5, 5.0), (20, 162.5, 5.0),
]


CHILD_AGE_MIN = 2
CHILD_AGE_MAX = 20
INFANT_AGE_MAX_MONTHS = 24


def _clamp_child_age(age_years: float) -> float:
    return max(CHILD_AGE_MIN, min(CHILD_AGE_MAX, age_years))


def _clamp_infant_age_months(age_months: float) -> float:
    return max(0.0, min(float(INFANT_AGE_MAX_MONTHS), age_months))


def parse_patient_age(age_str: str | None) -> float | None:
    if not age_str:
        return None
    text = age_str.strip().lower()
    months = re.search(r"(\d+(?:\.\d+)?)\s*m", text)
    if months:
        return float(months.group(1)) / 12.0
    years = re.search(r"(\d+(?:\.\d+)?)", text)
    if years:
        return float(years.group(1))
    return None


def is_female(sex: str | None) -> bool:
    return (sex or "").strip().lower().startswith("f")


def age_at_visit(patient_age_years: float, visit_date: datetime, reference: date | None = None) -> float:
    ref = reference or date.today()
    vdate = clinic_day(visit_date) if isinstance(visit_date, datetime) else visit_date
    elapsed_years = max(0.0, (ref - vdate).days / 365.25)
    return max(0.0, patient_age_years - elapsed_years)


def _interp(table: list[tuple[int, float, float]], age: float) -> tuple[float, float]:
    if not table:
        return 0.0, 1.0
    if age <= table[0][0]:
        return table[0][1], table[0][2]
    if age >= table[-1][0]:
        return table[-1][1], table[-1][2]
    for i in range(len(table) - 1):
        a0, m0, s0 = table[i]
        a1, m1, s1 = table[i + 1]
        if a0 <= age <= a1:
            if a1 == a0:
                return m0, s0
            t = (age - a0) / (a1 - a0)
            return m0 + t * (m1 - m0), s0 + t * (s1 - s0)
    return table[-1][1], table[-1][2]


def z_score(value: float, median: float, sd: float) -> float | None:
    if sd <= 0:
        return None
    return round((value - median) / sd, 2)


def _reference_table(chart: str, sex: str) -> list[tuple[int, float, float]]:
    female = is_female(sex)
    if chart == "infant":
        return GIRLS_INFANT if female else BOYS_INFANT
    return GIRLS_CHILD if female else BOYS_CHILD


def _build_curves(table: list[tuple[int, float, float]], x_key: str) -> list[dict]:
    curves = []
    for age, median, sd in table:
        curves.append({
            x_key: age,
            "sd_m2": round(median - 2 * sd, 1),
            "sd_m1": round(median - sd, 1),
            "sd_0": round(median, 1),
            "sd_p1": round(median + sd, 1),
            "sd_p2": round(median + 2 * sd, 1),
        })
    return curves


def _score_measurement(
    height_cm: float,
    age: float,
    sex: str,
    chart: str,
) -> dict:
    table = _reference_table(chart, sex)
    x_key = "age_months" if chart == "infant" else "age_years"
    if chart == "infant":
        lookup_age = age * 12
        plot_age = _clamp_infant_age_months(lookup_age)
        out_of_range = lookup_age > INFANT_AGE_MAX_MONTHS
        median, sd = _interp(table, _clamp_infant_age_months(lookup_age))
    else:
        lookup_age = age
        plot_age = _clamp_child_age(age)
        out_of_range = age > CHILD_AGE_MAX or age < CHILD_AGE_MIN
        median, sd = _interp(table, _clamp_child_age(age))
    zs = z_score(height_cm, median, sd)
    result = {
        x_key: round(plot_age, 2),
        "height_cm": height_cm,
        "median_cm": round(median, 1),
        "sd_cm": round(sd, 2),
        "z_score": zs,
        "sd_score": zs,
        "out_of_range": out_of_range,
    }
    if chart == "child" and out_of_range:
        result["reference_note"] = f"Z-score vs age {CHILD_AGE_MAX}y CDC norms (patient age {round(age, 1)}y)"
    elif chart == "infant" and out_of_range:
        result["reference_note"] = f"Z-score vs age {INFANT_AGE_MAX_MONTHS}mo CDC norms"
    return result


def growth_chart_data(
    patient_age_years: float,
    sex: str,
    visits: list,
    mid_parental_height: float | None = None,
) -> dict:
    """Build CDC growth chart payload for infant (0–24 mo) and child (2–20 yr) charts."""
    infant_table = _reference_table("infant", sex)
    child_table = _reference_table("child", sex)

    history_points: list[dict] = []
    for visit in visits:
        if not visit.height:
            continue
        age_y = age_at_visit(patient_age_years, visit.visit_date)
        age_months = age_y * 12
        chart = "infant" if age_months <= 24 else "child"
        point = {
            "date": clinic_day(visit.visit_date).isoformat(),
            "age_years": round(age_y, 2),
            "age_months": round(age_months, 1),
            "height_cm": visit.height,
            "weight_kg": visit.weight,
            "bmi": visit.bmi,
            "chart": chart,
        }
        scored = _score_measurement(visit.height, age_y, sex, chart)
        point.update(scored)
        history_points.append(point)

    latest = history_points[-1] if history_points else None
    active_chart = latest["chart"] if latest else ("infant" if patient_age_years * 12 <= 24 else "child")
    within_cdc_range = patient_age_years <= CHILD_AGE_MAX

    return {
        "patient_age_years": round(patient_age_years, 2),
        "patient_age_months": round(patient_age_years * 12, 1),
        "sex": sex,
        "is_pediatric": patient_age_years < 18,
        "within_cdc_range": within_cdc_range,
        "cdc_age_max_years": CHILD_AGE_MAX,
        "mid_parental_height": mid_parental_height,
        "active_chart": active_chart,
        "charts": {
            "infant": {
                "label": "CDC Length-for-age (0–24 months)",
                "x_label": "Age (months)",
                "x_key": "age_months",
                "y_label": "Length / Height (cm)",
                "reference": "CDC",
                "x_min": 0,
                "x_max": INFANT_AGE_MAX_MONTHS,
                "curves": _build_curves(infant_table, "age_months"),
            },
            "child": {
                "label": "CDC Stature-for-age (2–20 years)",
                "x_label": "Age (years)",
                "x_key": "age_years",
                "y_label": "Stature (cm)",
                "reference": "CDC",
                "x_min": CHILD_AGE_MIN,
                "x_max": CHILD_AGE_MAX,
                "curves": _build_curves(child_table, "age_years"),
            },
        },
        "history": history_points,
        "latest": latest,
    }
