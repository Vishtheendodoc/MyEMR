"""Drug-comorbidity interaction checking."""

from sqlalchemy.orm import Session

from app.models import Comorbidity, DrugComorbidityInteraction


def check_drug_comorbidity_interactions(db: Session, generic_drug_id: int, comorbidities_list: list[str]):
    warnings = []
    for comorbidity_name in comorbidities_list:
        if not comorbidity_name.strip():
            continue
        comorbidity = (
            db.query(Comorbidity)
            .filter(Comorbidity.name.ilike(f"%{comorbidity_name.strip()}%"))
            .first()
        )
        if comorbidity:
            interactions = (
                db.query(DrugComorbidityInteraction)
                .filter_by(generic_drug_id=generic_drug_id, comorbidity_id=comorbidity.id)
                .all()
            )
            for interaction in interactions:
                warnings.append({
                    "drug": interaction.generic_drug.generic_name,
                    "comorbidity": interaction.comorbidity.name,
                    "type": interaction.interaction_type,
                    "severity": interaction.severity,
                    "recommendation": interaction.recommendation,
                })
    return warnings
