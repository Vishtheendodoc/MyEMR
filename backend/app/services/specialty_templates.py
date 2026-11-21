"""Specialty visit templates: field definitions, lab sync, diagnosis matching."""

import re
from datetime import date

from sqlalchemy.orm import Session

from app.models import ImagingResult, LabResult
from app.services.pcos_scoring import SCORING_ONLY_KEYS as PCOS_SCORING_KEYS
from app.services.thyroid_scoring import THYROID_SCORING_ONLY_KEYS

SCORING_ONLY_KEYS = PCOS_SCORING_KEYS | THYROID_SCORING_ONLY_KEYS

# Shared lab panels — individual components per panel
COMMON_PANELS: dict[str, dict] = {
    "rft": {
        "label": "RFT",
        "fields": {
            "rft_urea": "Urea",
            "rft_creatinine": "Creatinine",
            "rft_egfr": "eGFR",
            "rft_sodium": "Sodium",
            "rft_potassium": "Potassium",
            "rft_chloride": "Chloride",
        },
    },
    "lft": {
        "label": "LFT",
        "fields": {
            "lft_bilirubin_total": "Bilirubin (Total)",
            "lft_bilirubin_direct": "Bilirubin (Direct)",
            "lft_ast": "AST (SGOT)",
            "lft_alt": "ALT (SGPT)",
            "lft_alp": "ALP",
            "lft_albumin": "Albumin",
            "lft_protein_total": "Total Protein",
        },
    },
    "lipid": {
        "label": "Lipid Profile",
        "fields": {
            "lipid_tchol": "Total Cholesterol",
            "lipid_ldl": "LDL",
            "lipid_hdl": "HDL",
            "lipid_tg": "Triglycerides",
            "lipid_vldl": "VLDL",
        },
    },
    "urine": {
        "label": "Urine Routine",
        "fields": {
            "urine_appearance": "Appearance",
            "urine_protein": "Protein",
            "urine_glucose": "Glucose",
            "urine_pus_cells": "Pus Cells",
            "urine_rbc": "RBC",
            "urine_epithelial": "Epithelial Cells",
        },
    },
    "cbc": {
        "label": "CBC",
        "fields": {
            "cbc_hb": "Hb",
            "cbc_tlc": "TLC",
            "cbc_platelets": "Platelets",
            "cbc_pcv": "PCV / Hct",
            "cbc_rbc": "RBC Count",
        },
    },
}

STANDALONE_COMMON_FIELDS: dict[str, str] = {
    "urine_microalbumin": "Urine Microalbumin",
    "other_investigations": "Other Investigations",
}

COMMON_FIELD_LABELS: dict[str, str] = {}
for _panel in COMMON_PANELS.values():
    COMMON_FIELD_LABELS.update(_panel["fields"])
COMMON_FIELD_LABELS.update(STANDALONE_COMMON_FIELDS)

COMMON_FIELD_KEYS = list(COMMON_FIELD_LABELS.keys())

TEMPLATE_SPECIFIC_LABELS: dict[str, dict[str, str]] = {
    "diabetes": {
        "fbs": "FBS",
        "rbs": "RBS",
        "ppbs": "PPBS",
        "hba1c": "HbA1c",
    },
    "thyroid": {
        "tsh": "TSH",
        "ft4": "FT4",
        "ft3": "FT3",
        "total_t4": "Total T4",
        "tpo_antibodies": "TPO Antibodies",
        "tshr_ab": "TSHR Ab",
        "who_goitre_grade": "WHO Goitre Grade",
        "who_goitre_interpretation": "WHO Goitre Interpretation",
        "cas_total": "Clinical Activity Score (CAS)",
        "cas_interpretation": "CAS Interpretation",
        "ted_severity": "TED Severity (EUGOGO)",
        "ted_severity_label": "TED Severity Label",
        "proptosis": "Proptosis (mm)",
        **{key: label for key, label in [
            ("cas_spontaneous_pain", "CAS — Spontaneous pain"),
            ("cas_gaze_pain", "CAS — Gaze pain"),
            ("cas_eyelid_erythema", "CAS — Eyelid erythema"),
            ("cas_eyelid_swelling", "CAS — Eyelid swelling"),
            ("cas_conjunctival_redness", "CAS — Conjunctival redness"),
            ("cas_chemosis", "CAS — Chemosis"),
            ("cas_caruncle_inflammation", "CAS — Caruncle inflammation"),
        ]},
    },
    "pituitary": {
        "fsh": "FSH",
        "lh": "LH",
        "prl": "PRL",
        "testosterone": "Testosterone",
        "estradiol": "Estradiol",
        "tsh": "TSH",
        "free_t4": "Free T4",
        "cortisol_8am": "8am Cortisol",
        "cortisol_random": "Random Cortisol",
        "acth": "ACTH",
        "igf1": "IGF-1",
    },
    "pcos": {
        "fsh": "FSH",
        "lh": "LH",
        "prl": "PRL",
        "testosterone": "Testosterone",
        "estradiol": "Estradiol",
        "amh": "AMH",
        "usg_pelvis": "USG Pelvis",
        "ferriman_gallwey_total": "Modified Ferriman-Gallwey Score",
        "fg_interpretation": "FG Interpretation",
        "ludwig_grade": "Ludwig Alopecia Grade",
        **{key: label for key, label in [
            ("fg_upper_lip", "FG — Upper lip"),
            ("fg_chin", "FG — Chin"),
            ("fg_chest", "FG — Chest"),
            ("fg_upper_abdomen", "FG — Upper abdomen"),
            ("fg_lower_abdomen", "FG — Lower abdomen"),
            ("fg_upper_back", "FG — Upper back"),
            ("fg_lower_back", "FG — Lower back"),
            ("fg_thighs", "FG — Thighs"),
            ("fg_upper_arms", "FG — Upper arms"),
        ]},
    },
    "adrenal": {
        "cortisol_8am": "8am Cortisol",
        "cortisol_random": "Random Cortisol",
        "acth": "ACTH",
        "dhea_s": "DHEA-S",
        "aldosterone": "Aldosterone",
    },
    "bone": {
        "calcium": "Calcium",
        "phosphorus": "Phosphorus",
        "albumin": "Albumin",
        "alp": "ALP",
        "vitamin_d": "Vitamin D",
        "pth": "PTH",
        "dxa_t_score": "DEXA T-score",
        "dxa_z_score": "DEXA Z-score",
        "frax_major": "FRAX major osteoporotic %",
        "frax_hip": "FRAX hip fracture %",
        "fracture_history": "Fracture history",
        "therapy_duration": "Bone therapy and duration",
        "drug_holiday": "Drug holiday",
    },
    "diabetic_foot": {
        "foot_monofilament": "10 g monofilament",
        "foot_pulses": "Foot pulses",
        "foot_ulcer_grade": "Ulcer grade",
        "foot_risk": "Risk category",
        "foot_deformity": "Deformity",
        "foot_wound_notes": "Wound notes",
    },
    "gestational": {
        "gestational_age_weeks": "Gestational age (weeks)",
        "gdm_fasting": "Fasting glucose",
        "gdm_postmeal": "Post-meal glucose",
        "insulin_plan": "Insulin plan",
        "delivery_outcome": "Delivery outcome",
        "neonatal_outcome": "Neonatal outcome",
    },
    "pediatric": {
        "tanner_stage": "Pubertal stage",
        "bone_age": "Bone age",
        "growth_note": "Growth note",
    },
    "obesity": {
        "weight_goal_kg": "Weight goal (kg)",
        "body_composition": "Body composition",
        "obesity_therapy": "Therapy",
        "side_effects": "Side effects",
    },
}

ALL_TEMPLATES = list(TEMPLATE_SPECIFIC_LABELS.keys())

# Field key -> (lab test name, unit, reference range)
LAB_FIELD_MAP: dict[str, tuple[str, str | None, str | None]] = {
    "fbs": ("FBS", "mg/dL", "70–100"),
    "rbs": ("RBS", "mg/dL", "70–140"),
    "ppbs": ("PPBS", "mg/dL", "<140"),
    "hba1c": ("HbA1c", "%", "<7.0"),
    "tsh": ("TSH", "mIU/L", "0.4–4.5"),
    "ft4": ("FT4", "ng/dL", "0.8–1.8"),
    "ft3": ("FT3", "pg/mL", "2.3–4.2"),
    "total_t4": ("Total T4", "mcg/dL", "5.0–12.0"),
    "free_t4": ("Free T4", "ng/dL", "0.8–1.8"),
    "tpo_antibodies": ("TPO Antibodies", "IU/mL", "<35"),
    "tshr_ab": ("TSHR Ab", "IU/L", "<1.75"),
    "fsh": ("FSH", "mIU/mL", "age-adjusted"),
    "lh": ("LH", "mIU/mL", "age-adjusted"),
    "prl": ("PRL", "ng/mL", "4–23"),
    "testosterone": ("Testosterone", "ng/dL", "age/sex-adjusted"),
    "estradiol": ("Estradiol", "pg/mL", "age-adjusted"),
    "cortisol_8am": ("8am Cortisol", "mcg/dL", "5–25"),
    "cortisol_random": ("Random Cortisol", "mcg/dL", "5–25"),
    "acth": ("ACTH", "pg/mL", "7–63"),
    "igf1": ("IGF-1", "ng/mL", "age-adjusted"),
    "amh": ("AMH", "ng/mL", "age-adjusted"),
    "dhea_s": ("DHEA-S", "mcg/dL", "age-adjusted"),
    "aldosterone": ("Aldosterone", "ng/dL", "upright ref"),
    "vitamin_d": ("Vitamin D", "ng/mL", "30–100"),
    "pth": ("PTH", "pg/mL", "15–65"),
    "calcium": ("Calcium", "mg/dL", "8.5–10.5"),
    "phosphorus": ("Phosphorus", "mg/dL", "2.5–4.5"),
    "albumin": ("Albumin", "g/dL", "3.5–5.0"),
    "alp": ("ALP", "U/L", "44–147"),
    "dxa_t_score": ("DEXA T-score", "", "≥ -1.0"),
    "rft_urea": ("Urea", "mg/dL", "15–40"),
    "rft_creatinine": ("Creatinine", "mg/dL", "0.6–1.2"),
    "rft_egfr": ("eGFR", "mL/min", ">60"),
    "rft_sodium": ("Sodium", "mEq/L", "136–145"),
    "rft_potassium": ("Potassium", "mEq/L", "3.5–5.0"),
    "rft_chloride": ("Chloride", "mEq/L", "98–107"),
    "lft_bilirubin_total": ("Bilirubin (Total)", "mg/dL", "0.1–1.2"),
    "lft_bilirubin_direct": ("Bilirubin (Direct)", "mg/dL", "0–0.3"),
    "lft_ast": ("AST", "U/L", "10–40"),
    "lft_alt": ("ALT", "U/L", "7–56"),
    "lft_alp": ("ALP", "U/L", "44–147"),
    "lft_albumin": ("Albumin", "g/dL", "3.5–5.0"),
    "lft_protein_total": ("Total Protein", "g/dL", "6.0–8.3"),
    "lipid_tchol": ("Total Cholesterol", "mg/dL", "<200"),
    "lipid_ldl": ("LDL", "mg/dL", "<100"),
    "lipid_hdl": ("HDL", "mg/dL", ">40"),
    "lipid_tg": ("Triglycerides", "mg/dL", "<150"),
    "lipid_vldl": ("VLDL", "mg/dL", "5–40"),
    "gdm_fasting": ("FBS", "mg/dL", "70–100"),
    "gdm_postmeal": ("PPBS", "mg/dL", "<140"),
    "urine_appearance": ("Urine Appearance", "", ""),
    "urine_protein": ("Urine Protein", "", "Negative"),
    "urine_glucose": ("Urine Glucose", "", "Negative"),
    "urine_pus_cells": ("Urine Pus Cells", "/hpf", "0–5"),
    "urine_rbc": ("Urine RBC", "/hpf", "0–2"),
    "urine_epithelial": ("Urine Epithelial", "/hpf", "0–5"),
    "cbc_hb": ("Hb", "g/dL", "12–16"),
    "cbc_tlc": ("TLC", "/cumm", "4000–11000"),
    "cbc_platelets": ("Platelets", "/cumm", "150000–400000"),
    "cbc_pcv": ("PCV", "%", "36–46"),
    "cbc_rbc": ("RBC Count", "million/cumm", "4.5–5.5"),
    "urine_microalbumin": ("Urine Microalbumin", "mg/g creatinine", "<30"),
}

IMAGING_FIELD_MAP: dict[str, str] = {
    "usg_pelvis": "USG Pelvis",
    "mri_findings": "MRI",
}

# Textarea / free-text fields
TEXTAREA_FIELDS = {
    "other_investigations", "usg_pelvis", "urine_appearance",
    "fracture_history", "therapy_duration", "drug_holiday", "foot_wound_notes",
    "insulin_plan", "delivery_outcome", "neonatal_outcome", "growth_note",
    "body_composition", "obesity_therapy", "side_effects",
}

DIAGNOSIS_KEYWORDS: dict[str, list[str]] = {
    "thyroid": ["thyroid", "hypothyroid", "hyperthyroid", "graves", "hashimoto", "goiter", "thyrotoxic"],
    "diabetes": ["diabetes", "diabetic", "dm ", "dm,", "insulin resistance", "hba1c", "prediabetes"],
    "pituitary": ["pituitary", "prolactinoma", "acromegaly", "growth hormone", "gh deficiency", "microadenoma"],
    "pcos": ["pcos", "pmos", "polycystic", "ovarian syndrome", "hirsutism", "oligomenorrhea"],
    "adrenal": ["adrenal", "cushing", "addison", "pheochromocytoma", "hyperaldosteronism", "congenital adrenal"],
    "bone": ["osteoporosis", "osteopenia", "vitamin d", "hyperparathyroid", "bone metabolic", "dxa", "frax"],
    "diabetic_foot": ["diabetic foot", "foot ulcer", "neuropathy foot", "charcot"],
    "gestational": ["gestational", "gdm", "pregnancy diabetes", "antenatal glucose"],
    "pediatric": ["pediatric", "short stature", "puberty", "precocious", "delayed puberty"],
    "obesity": ["obesity", "overweight", "bariatric", "weight loss"],
}


def _build_field_labels() -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    for template, specific in TEMPLATE_SPECIFIC_LABELS.items():
        ordered: dict[str, str] = {}
        for key, label in specific.items():
            ordered[key] = label
        for key in COMMON_FIELD_KEYS:
            ordered[key] = COMMON_FIELD_LABELS[key]
        labels[template] = ordered
    return labels


FIELD_LABELS = _build_field_labels()


def list_template_options() -> list[dict]:
    return [
        {"id": t, "label": t.replace("_", " ").title()}
        for t in ALL_TEMPLATES
    ]


def get_template_field_list(template: str) -> list[dict]:
    labels = FIELD_LABELS.get(template, {})
    specific_keys = set(TEMPLATE_SPECIFIC_LABELS.get(template, {}).keys())
    rows = []
    for key, label in labels.items():
        if key in SCORING_ONLY_KEYS:
            continue
        if key in specific_keys:
            rows.append({
                "key": key, "label": label,
                "multiline": key in TEXTAREA_FIELDS,
                "group": "condition",
                "group_label": template.replace("_", " ").title(),
            })
    for panel_id, panel in COMMON_PANELS.items():
        for key, label in panel["fields"].items():
            if key in labels:
                rows.append({
                    "key": key, "label": label,
                    "multiline": key in TEXTAREA_FIELDS,
                    "group": panel_id,
                    "group_label": panel["label"],
                })
    for key, label in STANDALONE_COMMON_FIELDS.items():
        if key in labels:
            rows.append({
                "key": key, "label": label,
                "multiline": key in TEXTAREA_FIELDS,
                "group": "other",
                "group_label": "Other",
            })
    return rows


def suggest_template_from_diagnosis(diagnosis: str) -> str | None:
    text = (diagnosis or "").lower()
    if not text.strip():
        return None
    scores: dict[str, int] = {}
    for template, keywords in DIAGNOSIS_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[template] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


_RESULT_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z][A-Za-z0-9 /().+\-]{0,40}?)\s*[:\-]?\s*(?P<value><?\s*-?\d+(?:\.\d+)?)\s*(?P<unit>[%A-Za-zµμ/^0-9.]*)\s*$"
)
_FROM_VISIT = "From visit"


def investigation_results(text: str | None) -> list[tuple[str, str, str | None, str | None]]:
    """Known results written as their own line, such as 'HbA1c 7.2'."""
    from app.services.patient_360 import PARAM_BY_CODE, canonical_code

    found: list[tuple[str, str, str | None, str | None]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or len(line) > 80:
            continue
        match = _RESULT_LINE.match(line)
        if not match:
            continue
        code = canonical_code(match.group("name"))
        spec = PARAM_BY_CODE.get(code or "")
        if spec is None:
            continue
        unit = (match.group("unit") or "").strip() or spec.unit
        value = re.sub(r"\s+", "", match.group("value"))
        found.append((spec.name, value, unit, spec.reference_range))
    return found


def reflect_visit_labs(db: Session, visit) -> int:
    """Write visit template values and result lines onto the shared lab list.

    Saving the same visit again updates those rows. A result entered on the labs
    page is left as it is.
    """
    from app.services.clinic_time import clinic_day
    from app.services.observation_sync import remove_sourced_observations

    specialty_data = parse_specialty_data(visit.specialty_data)
    result_day = clinic_day(visit.visit_date) if visit.visit_date else date.today()
    desired: dict[str, tuple[str, str | None, str | None]] = {}
    for test_name, value, unit, ref in investigation_results(visit.investigation):
        desired[test_name] = (value, unit, ref)
    for key, raw in specialty_data.items():
        if key not in LAB_FIELD_MAP or raw is None or not str(raw).strip():
            continue
        test_name, unit, ref = LAB_FIELD_MAP[key]
        desired[test_name] = (str(raw).strip(), unit or None, ref or None)

    existing = (
        db.query(LabResult)
        .filter_by(patient_id=visit.patient_id, visit_id=visit.id)
        .order_by(LabResult.id.asc())
        .all()
    )
    grouped: dict[str, list[LabResult]] = {}
    for lab in existing:
        grouped.setdefault(lab.test_name, []).append(lab)

    changes = 0
    for test_name, (value, unit, ref) in desired.items():
        rows = grouped.get(test_name, [])
        managed = [row for row in rows if (row.notes or "").startswith(_FROM_VISIT)]
        if managed:
            row = managed[-1]
            if row.value != value or row.unit != unit or row.reference_range != ref or row.result_date != result_day:
                row.value = value
                row.unit = unit
                row.reference_range = ref
                row.result_date = result_day
                row.notes = _FROM_VISIT
                changes += 1
            for extra in managed[:-1]:
                remove_sourced_observations(db, "lab_result", extra.id)
                db.delete(extra)
                changes += 1
        elif not rows:
            db.add(LabResult(
                patient_id=visit.patient_id,
                visit_id=visit.id,
                test_name=test_name,
                value=value,
                unit=unit,
                reference_range=ref,
                result_date=result_day,
                notes=_FROM_VISIT,
            ))
            changes += 1

    for test_name, rows in grouped.items():
        if test_name in desired:
            continue
        for row in rows:
            if (row.notes or "").startswith(_FROM_VISIT):
                remove_sourced_observations(db, "lab_result", row.id)
                db.delete(row)
                changes += 1

    imaging_desired: dict[str, str] = {}
    for key, raw in specialty_data.items():
        if key in IMAGING_FIELD_MAP and raw is not None and str(raw).strip():
            imaging_desired[IMAGING_FIELD_MAP[key]] = str(raw).strip()
    for study, findings in imaging_desired.items():
        images = (
            db.query(ImagingResult)
            .filter_by(patient_id=visit.patient_id, visit_id=visit.id, study_type=study)
            .order_by(ImagingResult.id.asc())
            .all()
        )
        if images:
            current = images[-1]
            if current.findings != findings or current.report_date != result_day:
                current.findings = findings
                current.report_date = result_day
                changes += 1
            for extra in images[:-1]:
                db.delete(extra)
                changes += 1
        else:
            db.add(ImagingResult(
                patient_id=visit.patient_id,
                visit_id=visit.id,
                study_type=study,
                findings=findings,
                report_date=result_day,
            ))
            changes += 1
    return changes


def reflect_stored_visit_labs(db: Session) -> int:
    """Copy results already written on visits into the shared lab list. Safe to repeat."""
    from app.models import Visit
    from app.services.observation_sync import sync_visit_observations

    total = 0
    touched = []
    for visit in db.query(Visit).all():
        count = reflect_visit_labs(db, visit)
        if count:
            touched.append(visit)
            total += count
    for visit in touched:
        db.flush()
        sync_visit_observations(db, visit)
    if total:
        db.commit()
    return total


def sync_template_to_labs(
    db: Session,
    patient_id: int,
    visit_id: int,
    template: str | None,
    specialty_data: dict | None,
) -> int:
    from app.models import Visit

    visit = db.get(Visit, visit_id)
    if visit is None:
        return 0
    if specialty_data is not None:
        import json
        visit.specialty_data = json.dumps(specialty_data)
        visit.specialty_template = template
    return reflect_visit_labs(db, visit)


def parse_specialty_data(raw: str | None) -> dict:
    import json
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def specialty_fields_for_display(template: str | None, specialty_data: dict) -> list[dict]:
    if not template:
        return []
    labels = FIELD_LABELS.get(template, {})
    rows = []
    for key, label in labels.items():
        val = specialty_data.get(key)
        if val is not None and str(val).strip():
            rows.append({"key": key, "label": label, "value": str(val)})
    return rows


def build_prescription_investigations(visit) -> str | None:
    """Combine template lab fields and free-text investigations for the prescription PDF."""
    specialty_data = parse_specialty_data(visit.specialty_data)
    template = visit.specialty_template
    lines: list[str] = []

    if template:
        groups: dict[str, list[str]] = {}
        group_order: list[str] = []
        for field in get_template_field_list(template):
            key = field["key"]
            raw = specialty_data.get(key)
            if raw is None or not str(raw).strip():
                continue
            value = str(raw).strip()
            group_label = field.get("group_label") or "Other"
            entry = f"{field['label']}: {value}"
            if group_label not in groups:
                groups[group_label] = []
                group_order.append(group_label)
            groups[group_label].append(entry)

        panel_labels = {panel["label"] for panel in COMMON_PANELS.values()} | {"Other"}
        for group_label in group_order:
            parts = groups[group_label]
            if group_label in panel_labels and len(parts) > 1:
                lines.append(f"{group_label} — {', '.join(parts)}")
            elif group_label in panel_labels:
                lines.append(f"{group_label} — {parts[0]}")
            else:
                lines.extend(parts)

    free_text = (visit.investigation or "").strip()
    if free_text:
        if lines:
            lines.append("")
        lines.append(free_text)

    return "\n".join(lines).strip() if lines else None
