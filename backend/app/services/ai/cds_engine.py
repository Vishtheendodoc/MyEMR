"""Expanded CDS rules using specialty template data."""

import json
import re

from sqlalchemy.orm import Session

from app.models import LabResult, Prescription, Visit
from app.services.clinical_safety import check_drug_comorbidity_interactions
from app.services.prescription_utils import format_prescription_drug_name
from app.services.specialty_templates import parse_specialty_data


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"-?[\d.]+", str(value))
    return float(m.group()) if m else None


def _latest_lab(db: Session, patient_id: int, test_names: list[str]) -> LabResult | None:
    q = db.query(LabResult).filter(LabResult.patient_id == patient_id)
    for name in test_names:
        result = q.filter(LabResult.test_name.ilike(f"%{name}%")).order_by(LabResult.result_date.desc()).first()
        if result:
            return result
    return None


def _add(recs: list[dict], category: str, severity: str, source: str, recommendation: str):
    recs.append({
        "category": category,
        "severity": severity,
        "source": source,
        "recommendation": recommendation,
    })


def _template_value(specialty: dict, *keys: str) -> float | None:
    for key in keys:
        if key in specialty and specialty[key]:
            val = _parse_float(str(specialty[key]))
            if val is not None:
                return val
    return None


def _apply_thyroid_rules(recs: list[dict], specialty: dict):
    tsh = _template_value(specialty, "tsh")
    ft4 = _template_value(specialty, "ft4")
    if tsh is not None:
        if tsh > 10:
            _add(recs, "Thyroid", "high", "ATA", f"TSH {tsh} mIU/L — marked elevation. Initiate or review levothyroxine replacement.")
        elif tsh > 4.5:
            _add(recs, "Thyroid", "medium", "ATA", f"TSH {tsh} mIU/L elevated. Check FT4 and thyroid antibodies; adjust levothyroxine if on treatment.")
        elif tsh < 0.4:
            _add(recs, "Thyroid", "medium", "ATA", f"TSH {tsh} mIU/L suppressed. Evaluate hyperthyroidism or overtreatment.")
    if tsh and ft4 and tsh > 4.5 and ft4 < 0.8:
        _add(recs, "Thyroid", "high", "ATA", "Primary hypothyroidism pattern (high TSH, low FT4). Confirm and treat.")

    who = specialty.get("who_goitre_grade")
    if who == "2":
        _add(recs, "Thyroid", "medium", "WHO", "WHO Grade 2 goitre — visible enlargement. Consider ultrasound and thyroid function assessment.")
    elif who == "1":
        _add(recs, "Thyroid", "low", "WHO", "WHO Grade 1 goitre — palpable only. Monitor and evaluate if symptomatic.")

    cas_total = _template_value(specialty, "cas_total")
    if cas_total is not None:
        if cas_total >= 3:
            _add(recs, "Thyroid", "high", "EUGOGO", f"CAS {cas_total:.0f}/7 — active thyroid eye disease. Consider anti-inflammatory therapy and specialist referral.")
        elif cas_total > 0:
            _add(recs, "Thyroid", "low", "EUGOGO", f"CAS {cas_total:.0f}/7 — currently inactive TED. Monitor clinically.")

    ted = (specialty.get("ted_severity") or "").lower()
    if ted == "sight_threatening":
        _add(recs, "Thyroid", "high", "EUGOGO", "Sight-threatening thyroid eye disease — urgent ophthalmology/endocrine referral.")
    elif ted == "moderate_severe":
        _add(recs, "Thyroid", "high", "EUGOGO", "Moderate-to-severe TED — specialist assessment for immunosuppression or surgery.")
    elif ted == "mild":
        _add(recs, "Thyroid", "medium", "EUGOGO", "Mild TED — local measures, smoking cessation, euthyroid maintenance.")

    proptosis = _template_value(specialty, "proptosis")
    if proptosis is not None and proptosis >= 22:
        _add(recs, "Thyroid", "medium", "EUGOGO", f"Proptosis {proptosis} mm — assess for significant exophthalmos.")


def _apply_diabetes_rules(recs: list[dict], specialty: dict):
    hba1c = _template_value(specialty, "hba1c")
    fbs = _template_value(specialty, "fbs")
    ppbs = _template_value(specialty, "ppbs")
    if hba1c is not None:
        if hba1c >= 9:
            _add(recs, "Diabetes", "high", "ADA", f"HbA1c {hba1c}% — substantially above target. Intensify therapy; screen complications.")
        elif hba1c >= 7:
            _add(recs, "Diabetes", "medium", "ADA", f"HbA1c {hba1c}% above goal (<7% most adults). Review adherence and regimen.")
        else:
            _add(recs, "Diabetes", "low", "ADA", f"HbA1c {hba1c}% at or near target. Continue current plan.")
    if fbs is not None and fbs >= 126:
        _add(recs, "Diabetes", "medium", "ADA", f"Fasting glucose {fbs} mg/dL meets diabetes range (≥126). Confirm diagnosis if not established.")
    if ppbs is not None and ppbs >= 200:
        _add(recs, "Diabetes", "medium", "ADA", f"Post-prandial glucose {ppbs} mg/dL elevated (≥200). Assess glycemic control.")


def _apply_adrenal_rules(recs: list[dict], specialty: dict):
    cortisol = _template_value(specialty, "cortisol_8am", "cortisol_am", "cortisol")
    cortisol_random = _template_value(specialty, "cortisol_random")
    acth = _template_value(specialty, "acth")
    if cortisol is not None and cortisol > 25:
        _add(recs, "Adrenal", "medium", "Endocrine Society", f"Cortisol {cortisol} mcg/dL elevated. Consider Cushing syndrome workup (dexamethasone suppression, imaging).")
    if cortisol is not None and cortisol < 5:
        _add(recs, "Adrenal", "high", "Endocrine Society", f"Cortisol {cortisol} mcg/dL low. Evaluate adrenal insufficiency; stress-dose steroids if symptomatic.")
    if acth is not None and cortisol is not None and acth > 63 and cortisol < 5:
        _add(recs, "Adrenal", "high", "Endocrine Society", "High ACTH with low cortisol — primary adrenal insufficiency likely.")


def _apply_bone_rules(recs: list[dict], specialty: dict):
    vit_d = _template_value(specialty, "vitamin_d")
    t_score = _template_value(specialty, "dxa_t_score")
    pth = _template_value(specialty, "pth")
    calcium = _template_value(specialty, "calcium")
    if vit_d is not None and vit_d < 20:
        _add(recs, "Bone", "medium", "Endocrine Society", f"Vitamin D {vit_d} ng/mL — deficiency. Supplement and recheck in 8–12 weeks.")
    if t_score is not None and t_score <= -2.5:
        _add(recs, "Bone", "high", "NOF", f"DEXA T-score {t_score} — osteoporosis. Assess fracture risk; consider bisphosphonate or anabolic therapy.")
    elif t_score is not None and t_score <= -1.0:
        _add(recs, "Bone", "medium", "NOF", f"DEXA T-score {t_score} — osteopenia. Optimize calcium, vitamin D, and fall prevention.")
    if pth is not None and pth > 65 and calcium is not None and calcium > 10.5:
        _add(recs, "Bone", "medium", "Endocrine Society", "Elevated PTH with hypercalcemia — evaluate primary hyperparathyroidism.")


def _apply_pituitary_rules(recs: list[dict], specialty: dict):
    prolactin = _template_value(specialty, "prl", "prolactin")
    igf1 = _template_value(specialty, "igf1")
    if prolactin is not None and prolactin > 100:
        _add(recs, "Pituitary", "high", "Endocrine Society", f"Prolactin {prolactin} ng/mL markedly elevated. MRI pituitary; consider dopamine agonist.")
    elif prolactin is not None and prolactin > 23:
        _add(recs, "Pituitary", "medium", "Endocrine Society", f"Prolactin {prolactin} ng/mL elevated. Repeat fasting; rule out macroprolactin and medications.")
    if igf1 is not None and igf1 > 300:
        _add(recs, "Pituitary", "medium", "Endocrine Society", f"IGF-1 {igf1} ng/mL elevated. Consider acromegaly screening and pituitary MRI.")


def _apply_pcos_rules(recs: list[dict], specialty: dict):
    lh = _template_value(specialty, "lh")
    fsh = _template_value(specialty, "fsh")
    testosterone = _template_value(specialty, "testosterone")
    amh = _template_value(specialty, "amh")
    fg_total = _template_value(specialty, "ferriman_gallwey_total")
    ludwig = specialty.get("ludwig_grade")
    if lh and fsh and fsh > 0 and lh / fsh >= 2:
        _add(recs, "PCOS", "medium", "Rotterdam Criteria", f"LH/FSH ratio {lh/fsh:.1f} — supports PCOS workup. Correlate with clinical hyperandrogenism and ovarian morphology.")
    if testosterone is not None and testosterone > 50:
        _add(recs, "PCOS", "medium", "Endocrine Society", f"Testosterone {testosterone} ng/dL elevated — assess hyperandrogenism.")
    if amh is not None and amh > 4.5:
        _add(recs, "PCOS", "low", "ESHRE", f"AMH {amh} ng/mL elevated — may support PCO morphology; interpret with age and assay.")
    if fg_total is not None and fg_total >= 6:
        _add(recs, "PCOS", "medium", "Rotterdam Criteria", f"Modified Ferriman-Gallwey score {fg_total:.0f}/36 — clinical hirsutism (hyperandrogenism criterion).")
    elif fg_total is not None and fg_total < 6:
        _add(recs, "PCOS", "low", "Rotterdam Criteria", f"Modified Ferriman-Gallwey score {fg_total:.0f}/36 — below South Asian hirsutism threshold.")
    if ludwig in ("II", "III"):
        _add(recs, "PCOS", "medium", "Rotterdam Criteria", f"Ludwig Grade {ludwig} androgenic alopecia — supports clinical hyperandrogenism.")
    elif ludwig == "I":
        _add(recs, "PCOS", "low", "Rotterdam Criteria", "Ludwig Grade I androgenic alopecia — mild crown thinning.")


def get_cds_recommendations(db: Session, visit: Visit) -> list[dict]:
    recommendations: list[dict] = []
    diagnosis = (visit.diagnosis or "").lower()
    comorbidities = [c.strip() for c in (visit.comorbidities or "").split(",") if c.strip()]
    specialty = parse_specialty_data(visit.specialty_data)
    template = visit.specialty_template or specialty.get("condition")

    # Lab-based rules (includes auto-synced labs from templates)
    hba1c = _latest_lab(db, visit.patient_id, ["hba1c", "hb a1c", "glycated"])
    tsh = _latest_lab(db, visit.patient_id, ["tsh"])
    egfr_lab = _latest_lab(db, visit.patient_id, ["egfr", "gfr"])

    if hba1c and not _template_value(specialty, "hba1c"):
        val = _parse_float(hba1c.value)
        if val is not None:
            if val >= 9:
                _add(recommendations, "Diabetes", "high", "ADA Guidelines", f"HbA1c {val}% substantially above target.")
            elif val >= 7:
                _add(recommendations, "Diabetes", "medium", "ADA Guidelines", f"HbA1c {val}% above general target (<7%).")

    if tsh and not _template_value(specialty, "tsh"):
        val = _parse_float(tsh.value)
        if val is not None:
            if val > 4.5:
                _add(recommendations, "Thyroid", "medium", "ATA Guidelines", f"TSH {val} mIU/L elevated.")
            elif val < 0.4:
                _add(recommendations, "Thyroid", "medium", "ATA Guidelines", f"TSH {val} mIU/L suppressed.")

    if egfr_lab:
        val = _parse_float(egfr_lab.value)
        if val is not None and val < 30:
            _add(recommendations, "Renal", "high", "KDIGO", f"eGFR {val} — severe CKD. Avoid nephrotoxic drugs.")

    if "diabetes" in diagnosis and visit.bmi and visit.bmi >= 30:
        _add(recommendations, "Obesity", "medium", "ADA", f"BMI {visit.bmi} with diabetes — consider GLP-1 agonist or SGLT2i.")

    prescriptions = db.query(Prescription).filter_by(visit_id=visit.id).all()
    for rx in prescriptions:
        if rx.brand_medication and comorbidities:
            for w in check_drug_comorbidity_interactions(db, rx.brand_medication.generic_drug_id, comorbidities):
                _add(recommendations, "Drug Safety", w.get("severity") or "medium", "Formulary Rules",
                     f"{format_prescription_drug_name(rx)}: {w.get('recommendation')}")

    # Template-specific rules (visit-entered values)
    if template == "thyroid":
        _apply_thyroid_rules(recommendations, specialty)
    elif template == "diabetes":
        _apply_diabetes_rules(recommendations, specialty)
    elif template == "adrenal":
        _apply_adrenal_rules(recommendations, specialty)
    elif template == "bone":
        _apply_bone_rules(recommendations, specialty)
    elif template == "pituitary":
        _apply_pituitary_rules(recommendations, specialty)
    elif template == "pcos":
        _apply_pcos_rules(recommendations, specialty)

    if not recommendations:
        _add(recommendations, "General", "low", "System", "No specific alerts. Continue standard endocrine follow-up.")

    return recommendations
