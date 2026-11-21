"""Default rules and drug-pair prompts. Existing rows are left as edited."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models import ClinicalRule, DrugPairInteraction

RULES: list[dict] = [
    {
        "code": "hba1c_review",
        "version": "1",
        "domain": "diabetes",
        "title": "HbA1c is above a common review level",
        "severity": "high",
        "guideline_reference": "ADA Standards of Care, glycemic assessment",
        "explanation": "The latest HbA1c is at or above the configured review level. Review glucose records and the current plan. This is not a diagnosis and it does not start or change a medicine.",
        "recommended_review": "Review diabetes treatment with the patient.",
        "observation_code": "hba1c",
        "direction": "high",
        "threshold_low": None,
        "threshold_high": 9.0,
    },
    {
        "code": "hba1c_rise",
        "version": "1",
        "domain": "diabetes",
        "title": "HbA1c has risen",
        "severity": "medium",
        "guideline_reference": "ADA Standards of Care, glycemic assessment",
        "explanation": "HbA1c is higher than the previous result by at least one point. Review adherence and the current plan. A rise is not a new diagnosis.",
        "recommended_review": "Compare the two HbA1c results and the current medicines.",
        "observation_code": "hba1c",
        "direction": "custom",
        "threshold_low": None,
        "threshold_high": 1.0,
    },
    {
        "code": "hypoglycemia_review",
        "version": "1",
        "domain": "diabetes",
        "title": "A low glucose value is on the chart",
        "severity": "high",
        "guideline_reference": "ADA Standards of Care, hypoglycemia",
        "explanation": "A glucose value is below the configured level. Review symptoms, timing, and doses. One low value does not establish a hypoglycemia diagnosis.",
        "recommended_review": "Review the low reading with the patient.",
        "observation_code": "cgm_glucose",
        "direction": "custom",
        "threshold_low": 70.0,
        "threshold_high": None,
    },
    {
        "code": "renal_review",
        "version": "1",
        "domain": "diabetes",
        "title": "Kidney function needs review",
        "severity": "high",
        "guideline_reference": "KDIGO CKD evaluation",
        "explanation": "eGFR is below the configured level, or creatinine is above its configured level. Review kidney function before dose decisions. The chart was not changed.",
        "recommended_review": "Review renal function and doses that depend on it.",
        "observation_code": "egfr",
        "direction": "custom",
        "threshold_low": 45.0,
        "threshold_high": 1.5,
    },
    {
        "code": "albuminuria_review",
        "version": "1",
        "domain": "diabetes",
        "title": "Urine albumin is above a common review level",
        "severity": "medium",
        "guideline_reference": "KDIGO diabetes and CKD",
        "explanation": "Urine albumin-creatinine ratio is at or above the configured level. Review kidney and blood-pressure care. This is not a diagnosis.",
        "recommended_review": "Review albuminuria and kidney care.",
        "observation_code": "uacr",
        "direction": "high",
        "threshold_low": None,
        "threshold_high": 30.0,
    },
    {
        "code": "screening_gap",
        "version": "1",
        "domain": "diabetes",
        "title": "A diabetes complication check is not on the chart",
        "severity": "medium",
        "guideline_reference": "ADA Standards of Care, complication screening",
        "explanation": "Diabetes is recorded and a urine albumin result from the last year is not on the chart. This is a reminder to review screening, not an order.",
        "recommended_review": "Review whether nephropathy screening is due.",
        "observation_code": "uacr",
        "direction": "custom",
        "threshold_low": None,
        "threshold_high": 365.0,
    },
    {
        "code": "tsh_review",
        "version": "1",
        "domain": "thyroid",
        "title": "TSH is above a common review level",
        "severity": "high",
        "guideline_reference": "ATA hypothyroidism guidance",
        "explanation": "TSH is at or above the configured level. Review symptoms and thyroid treatment. One TSH result does not establish a diagnosis and does not start a medicine.",
        "recommended_review": "Review thyroid function and current treatment.",
        "observation_code": "tsh",
        "direction": "high",
        "threshold_low": None,
        "threshold_high": 10.0,
    },
    {
        "code": "tsh_on_levothyroxine",
        "version": "1",
        "domain": "thyroid",
        "title": "TSH is low on levothyroxine",
        "severity": "medium",
        "guideline_reference": "ATA hypothyroidism treatment",
        "explanation": "TSH is below the configured level and levothyroxine is on a prescription. Review the dose with the patient. The prescription was not changed.",
        "recommended_review": "Review the levothyroxine dose.",
        "observation_code": "tsh",
        "direction": "custom",
        "threshold_low": 0.1,
        "threshold_high": None,
    },
    {
        "code": "pregnancy_tsh",
        "version": "1",
        "domain": "thyroid",
        "title": "TSH needs review in a pregnancy note",
        "severity": "high",
        "guideline_reference": "ATA thyroid disease in pregnancy",
        "explanation": "A visit mentions pregnancy and TSH is above the configured level. Review thyroid care for pregnancy. This does not change treatment.",
        "recommended_review": "Review thyroid results in the pregnancy context.",
        "observation_code": "tsh",
        "direction": "custom",
        "threshold_low": None,
        "threshold_high": 2.5,
    },
    {
        "code": "t_score_review",
        "version": "1",
        "domain": "bone",
        "title": "T-score is at a common osteoporosis review level",
        "severity": "high",
        "guideline_reference": "Bone Health and Osteoporosis Foundation",
        "explanation": "The latest T-score is at or below the configured level. Review fracture history and treatment. This does not start a medicine.",
        "recommended_review": "Review bone density and treatment.",
        "observation_code": "t_score",
        "direction": "low",
        "threshold_low": -2.5,
        "threshold_high": None,
    },
    {
        "code": "vitamin_d_review",
        "version": "1",
        "domain": "bone",
        "title": "Vitamin D is below a common review level",
        "severity": "medium",
        "guideline_reference": "Endocrine Society vitamin D guidance",
        "explanation": "Vitamin D is below the configured level. Review replacement and the plan to repeat the test. This does not prescribe a dose.",
        "recommended_review": "Review vitamin D and related bone labs.",
        "observation_code": "vitamin_d",
        "direction": "low",
        "threshold_low": 20.0,
        "threshold_high": None,
    },
    {
        "code": "prolactin_review",
        "version": "1",
        "domain": "pituitary",
        "title": "Prolactin is above a common review level",
        "severity": "high",
        "guideline_reference": "Endocrine Society hyperprolactinemia guidance",
        "explanation": "Prolactin is at or above the configured level. Review medicines, repeat testing, and imaging needs. This is not a diagnosis.",
        "recommended_review": "Review the prolactin result.",
        "observation_code": "prolactin",
        "direction": "high",
        "threshold_low": None,
        "threshold_high": 100.0,
    },
    {
        "code": "igf1_review",
        "version": "1",
        "domain": "pituitary",
        "title": "IGF-1 is above a common review level",
        "severity": "medium",
        "guideline_reference": "Endocrine Society acromegaly guidance",
        "explanation": "IGF-1 is at or above the configured level. Review symptoms and whether further testing is needed. This is not a diagnosis.",
        "recommended_review": "Review the IGF-1 result.",
        "observation_code": "igf1",
        "direction": "high",
        "threshold_low": None,
        "threshold_high": 300.0,
    },
    {
        "code": "cortisol_review",
        "version": "1",
        "domain": "adrenal",
        "title": "Cortisol is below a common review level",
        "severity": "high",
        "guideline_reference": "Endocrine Society adrenal insufficiency guidance",
        "explanation": "Cortisol is below the configured level. Review adrenal insufficiency and emergency steroid education. This does not start steroid treatment.",
        "recommended_review": "Review cortisol and steroid education.",
        "observation_code": "cortisol",
        "direction": "low",
        "threshold_low": 5.0,
        "threshold_high": None,
    },
    {
        "code": "pcos_weight_rise",
        "version": "1",
        "domain": "pcos",
        "title": "Weight has risen on a PCOS chart",
        "severity": "medium",
        "guideline_reference": "International evidence-based PCOS guideline",
        "explanation": "PCOS is recorded and weight is at least 5% higher than an earlier visit. Review metabolic care. This does not change treatment.",
        "recommended_review": "Review weight and metabolic results.",
        "observation_code": "weight",
        "direction": "custom",
        "threshold_low": None,
        "threshold_high": 5.0,
    },
]

DRUG_PAIRS: list[dict] = [
    {
        "generic_a": "levothyroxine",
        "generic_b": "calcium",
        "severity": "medium",
        "recommendation": "Review the timing of levothyroxine and calcium. The prescription was not changed.",
    },
    {
        "generic_a": "levothyroxine",
        "generic_b": "iron",
        "severity": "medium",
        "recommendation": "Review the timing of levothyroxine and iron. The prescription was not changed.",
    },
    {
        "generic_a": "prednisolone",
        "generic_b": "ibuprofen",
        "severity": "medium",
        "recommendation": "Review combined steroid and NSAID use. The prescription was not changed.",
    },
]


def seed_platform(db: Session) -> None:
    for row in RULES:
        if db.query(ClinicalRule).filter_by(code=row["code"]).first():
            continue
        db.add(ClinicalRule(**row))
    for row in DRUG_PAIRS:
        found = (
            db.query(DrugPairInteraction)
            .filter_by(generic_a=row["generic_a"], generic_b=row["generic_b"])
            .first()
        )
        if found:
            continue
        db.add(DrugPairInteraction(**row))
    db.commit()


def seed_connection(connection) -> None:
    """Insert defaults during an Alembic upgrade. Skips codes that already exist."""
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    if "clinical_rule" in names:
        for row in RULES:
            exists = connection.execute(
                text("SELECT 1 FROM clinical_rule WHERE code = :code"),
                {"code": row["code"]},
            ).first()
            if exists:
                continue
            connection.execute(
                text(
                    "INSERT INTO clinical_rule (code, version, domain, title, severity, guideline_reference, "
                    "explanation, recommended_review, observation_code, direction, threshold_low, threshold_high, active, created_at) "
                    "VALUES (:code, :version, :domain, :title, :severity, :guideline_reference, :explanation, "
                    ":recommended_review, :observation_code, :direction, :threshold_low, :threshold_high, :active, :created_at)"
                ),
                {**row, "active": True, "created_at": now},
            )
    if "drug_pair_interaction" in names:
        for row in DRUG_PAIRS:
            exists = connection.execute(
                text("SELECT 1 FROM drug_pair_interaction WHERE generic_a = :generic_a AND generic_b = :generic_b"),
                row,
            ).first()
            if exists:
                continue
            connection.execute(
                text(
                    "INSERT INTO drug_pair_interaction (generic_a, generic_b, severity, recommendation) "
                    "VALUES (:generic_a, :generic_b, :severity, :recommendation)"
                ),
                row,
            )
