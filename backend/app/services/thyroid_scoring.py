"""WHO goitre classification, CAS, and EUGOGO thyroid eye disease grading."""

WHO_GOITRE_GRADES: dict[str, str] = {
    "0": "Grade 0 — no goitre palpable or visible",
    "1": "Grade 1 — palpable but not visible with neck in normal position",
    "2": "Grade 2 — palpable and visible with neck in normal position",
}

CAS_ITEMS: list[tuple[str, str]] = [
    ("cas_spontaneous_pain", "Spontaneous retrobulbar pain"),
    ("cas_gaze_pain", "Pain on attempted upward/downward gaze"),
    ("cas_eyelid_erythema", "Eyelid erythema"),
    ("cas_eyelid_swelling", "Eyelid swelling"),
    ("cas_conjunctival_redness", "Conjunctival redness"),
    ("cas_chemosis", "Chemosis"),
    ("cas_caruncle_inflammation", "Caruncle/plica inflammation"),
]

CAS_ITEM_KEYS = {key for key, _ in CAS_ITEMS}

TED_SEVERITY_GRADES: dict[str, str] = {
    "N": "No signs or symptoms",
    "mild": "Mild — minor lid retraction, mild soft tissue changes, normal-range proptosis",
    "moderate_severe": "Moderate-to-severe — significant lid retraction, soft tissue involvement, proptosis, or diplopia",
    "sight_threatening": "Sight-threatening — dysthyroid optic neuropathy or corneal breakdown",
}

THYROID_SCORING_ONLY_KEYS = (
    {"who_goitre_grade", "who_goitre_interpretation", "cas_total", "cas_interpretation",
     "ted_severity", "ted_severity_label", "proptosis"}
    | CAS_ITEM_KEYS
)


def interpret_cas(item_scores: dict[str, bool | int | str]) -> dict:
    total = sum(1 for key, _ in CAS_ITEMS if str(item_scores.get(key, "")).lower() in ("1", "true", "yes"))
    active = total >= 3
    return {
        "total": total,
        "max_score": 7,
        "active": active,
        "interpretation": (
            f"Clinical Activity Score {total}/7 — "
            + ("active thyroid eye disease (≥3)" if active else "inactive thyroid eye disease (<3)")
        ),
    }


def interpret_who_goitre(grade: str) -> dict:
    g = (grade or "").strip()
    if g not in WHO_GOITRE_GRADES:
        raise ValueError("WHO goitre grade must be 0, 1, or 2")
    return {"grade": g, "description": WHO_GOITRE_GRADES[g]}


def interpret_ted_severity(severity: str) -> dict:
    s = (severity or "").strip().lower()
    if s not in TED_SEVERITY_GRADES:
        raise ValueError("Invalid thyroid eye disease severity grade")
    return {"severity": s, "description": TED_SEVERITY_GRADES[s]}
