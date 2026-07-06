"""Modified Ferriman-Gallwey and Ludwig alopecia scoring for PCOS."""

from pydantic import BaseModel, Field

# Nine androgen-sensitive sites (modified Ferriman-Gallwey)
FG_SITES: list[tuple[str, str]] = [
    ("fg_upper_lip", "Upper lip"),
    ("fg_chin", "Chin"),
    ("fg_chest", "Chest"),
    ("fg_upper_abdomen", "Upper abdomen"),
    ("fg_lower_abdomen", "Lower abdomen"),
    ("fg_upper_back", "Upper back"),
    ("fg_lower_back", "Lower back"),
    ("fg_thighs", "Thighs"),
    ("fg_upper_arms", "Upper arms"),
]

FG_SITE_KEYS = {key for key, _ in FG_SITES}
SCORING_ONLY_KEYS = FG_SITE_KEYS | {"ferriman_gallwey_total", "ludwig_grade", "fg_interpretation"}

LUDWIG_GRADES = {
    "I": "Grade I — perceptible thinning on crown, frontal hairline preserved",
    "II": "Grade II — pronounced rarefaction on crown, frontal hairline preserved",
    "III": "Grade III — full baldness on crown, frontal hairline preserved",
}


class FerrimanGallweyInput(BaseModel):
    fg_upper_lip: int = Field(ge=0, le=4, default=0)
    fg_chin: int = Field(ge=0, le=4, default=0)
    fg_chest: int = Field(ge=0, le=4, default=0)
    fg_upper_abdomen: int = Field(ge=0, le=4, default=0)
    fg_lower_abdomen: int = Field(ge=0, le=4, default=0)
    fg_upper_back: int = Field(ge=0, le=4, default=0)
    fg_lower_back: int = Field(ge=0, le=4, default=0)
    fg_thighs: int = Field(ge=0, le=4, default=0)
    fg_upper_arms: int = Field(ge=0, le=4, default=0)
    ethnicity: str = "south_asian"


def interpret_ferriman_gallwey(total: int, ethnicity: str = "south_asian") -> dict:
    eth = (ethnicity or "south_asian").lower().replace(" ", "_")
    if eth in ("caucasian", "white", "european"):
        threshold = 8
    elif eth in ("south_asian", "asian", "indian"):
        threshold = 6
    elif eth in ("middle_eastern", "hispanic", "latino"):
        threshold = 6
    else:
        threshold = 8

    if total < threshold:
        severity = "Normal"
        hyperandrogenism = False
    elif total < 15:
        severity = "Mild hirsutism"
        hyperandrogenism = True
    elif total < 25:
        severity = "Moderate hirsutism"
        hyperandrogenism = True
    else:
        severity = "Severe hirsutism"
        hyperandrogenism = True

    return {
        "total": total,
        "max_score": 36,
        "threshold": threshold,
        "severity": severity,
        "hyperandrogenism_criterion": hyperandrogenism,
        "interpretation": (
            f"Modified Ferriman-Gallwey score {total}/36 — {severity}. "
            f"Threshold ≥{threshold} for clinical hirsutism ({eth.replace('_', ' ')})."
        ),
    }


def calculate_ferriman_gallwey(data: FerrimanGallweyInput) -> dict:
    site_scores = {key: getattr(data, key) for key, _ in FG_SITES}
    total = sum(site_scores.values())
    result = interpret_ferriman_gallwey(total, data.ethnicity)
    result["site_scores"] = site_scores
    return result


def interpret_ludwig(grade: str) -> dict:
    g = (grade or "").strip().upper()
    if g not in LUDWIG_GRADES:
        raise ValueError("Ludwig grade must be I, II, or III")
    return {
        "grade": g,
        "description": LUDWIG_GRADES[g],
        "androgenic_alopecia": True,
    }
