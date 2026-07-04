"""Helpers for prescription drug display and formatting."""

import re

FORMULATION_ABBREV = {
    'tablet': 'Tab',
    'capsule': 'Cap',
    'injection': 'Inj',
    'syrup': 'Syp',
    'suspension': 'Susp',
    'gel': 'Gel',
    'cream': 'Cream',
    'powder': 'Powder',
    'ointment': 'Oint',
    'drops': 'Drops',
    'inhaler': 'Inh',
    'solution': 'Sol',
}


def formulation_abbrev(formulation):
    if not formulation:
        return ''
    return FORMULATION_ABBREV.get(formulation.strip().lower(), formulation.strip())


def format_brand_label(brand):
    """Display name for dropdowns: Tab Glycomet 500mg"""
    if not brand:
        return ''
    parts = []
    abbrev = formulation_abbrev(brand.formulation)
    if abbrev:
        parts.append(abbrev)
    parts.append(brand.brand_name)
    if brand.strength:
        parts.append(brand.strength)
    return ' '.join(parts)


def format_prescription_drug_name(prescription):
    if getattr(prescription, 'custom_drug_name', None):
        return prescription.custom_drug_name.strip()
    brand = prescription.brand_medication
    if not brand:
        return 'Unknown medication'
    return format_brand_label(brand)


def format_prescription_generic_name(prescription):
    if getattr(prescription, 'custom_drug_name', None):
        custom_generic = getattr(prescription, 'custom_generic_name', None)
        return custom_generic.strip() if custom_generic else '-'
    brand = prescription.brand_medication
    if brand and brand.generic_drug:
        return brand.generic_drug.generic_name
    return ''


HAS_UNIT_RE = re.compile(r'mg|mcg|g\b|iu|%', re.I)


def ensure_mg_unit(dosage):
    dose = (dosage or '').strip()
    if not dose or HAS_UNIT_RE.search(dose):
        return dose
    return f'{dose} mg'


def suggest_prescription_dosage(brand):
    if not brand or is_insulin_brand(brand):
        return None
    strength = (brand.strength or '').strip()
    if not strength:
        return None
    formulation = (brand.formulation or '').strip().lower()
    if formulation in ('tablet', 'capsule'):
        return ensure_mg_unit(strength)
    return strength


def format_insulin_dose(value):
    """Format a single insulin dose with U for units."""
    dose = (value or '').strip()
    if not dose:
        return ''
    if dose.lower().endswith('u') or dose.lower().endswith('units'):
        return dose
    return f'{dose}U'


def format_prescription_dosage(prescription):
    morning = getattr(prescription, 'dose_morning', None)
    afternoon = getattr(prescription, 'dose_afternoon', None)
    evening = getattr(prescription, 'dose_evening', None)
    if morning or afternoon or evening:
        parts = []
        if morning:
            parts.append(f'M: {format_insulin_dose(morning)}')
        if afternoon:
            parts.append(f'A: {format_insulin_dose(afternoon)}')
        if evening:
            parts.append(f'E: {format_insulin_dose(evening)}')
        return ' | '.join(parts)
    dosage = prescription.dosage or '-'
    if dosage == '-':
        return dosage
    if getattr(prescription, 'custom_drug_name', None):
        return dosage
    brand = prescription.brand_medication
    if brand:
        formulation = (brand.formulation or '').strip().lower()
        if formulation in ('tablet', 'capsule'):
            return ensure_mg_unit(dosage)
    return dosage


def is_insulin_brand(brand):
    if not brand:
        return False
    if brand.formulation and brand.formulation.strip().lower() == 'injection':
        generic = (brand.generic_drug.generic_name or '').lower() if brand.generic_drug else ''
        if 'semaglutide' in generic:
            return False
        insulin_keywords = ('insulin', 'glargine', 'lispro', 'aspart', 'degludec', 'nph', 'human insulin')
        if any(kw in generic for kw in insulin_keywords):
            return True
        brand_lower = brand.brand_name.lower()
        insulin_brand_keywords = (
            'insulin', 'huminsulin', 'humalog', 'basalog', 'basaglar', 'basugine',
            'tresiba', 'novorapid', 'fiasp', 'ryzodeg', 'xsulin', 'lupisulin', 'xglar', 'lyumjev',
        )
        if any(kw in brand_lower for kw in insulin_brand_keywords):
            return True
    return False


def get_or_create_manual_entry_brand():
    """Placeholder brand for prescriptions entered manually (not in database)."""
    from models import db, GenericDrug, BrandMedication

    generic = GenericDrug.query.filter_by(generic_name='Custom / Manual Entry').first()
    if not generic:
        generic = GenericDrug(
            generic_name='Custom / Manual Entry',
            drug_class='Other',
            indication='Manually entered prescription',
        )
        db.session.add(generic)
        db.session.flush()

    brand = BrandMedication.query.filter_by(
        brand_name='Manual Entry',
        generic_drug_id=generic.id,
    ).first()
    if not brand:
        brand = BrandMedication(
            brand_name='Manual Entry',
            generic_drug_id=generic.id,
            formulation='Other',
        )
        db.session.add(brand)
        db.session.commit()
    return brand


def ensure_prescription_columns():
    """Add prescription columns to existing SQLite databases."""
    from sqlalchemy import inspect, text
    from models import db

    inspector = inspect(db.engine)
    if 'prescription' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('prescription')}
    statements = []
    column_defs = {
        'custom_drug_name': 'VARCHAR(300)',
        'custom_generic_name': 'VARCHAR(200)',
        'dose_morning': 'VARCHAR(50)',
        'dose_afternoon': 'VARCHAR(50)',
        'dose_evening': 'VARCHAR(50)',
    }
    for name, col_type in column_defs.items():
        if name not in columns:
            statements.append(f'ALTER TABLE prescription ADD COLUMN {name} {col_type}')

    if not statements:
        return

    with db.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def get_brand_prescription_counts(doctor_id=None):
    """Count prescriptions per database brand (excludes custom/manual entries)."""
    from sqlalchemy import func, or_
    from models import db, Prescription, Visit

    query = (
        db.session.query(Prescription.brand_medication_id, func.count(Prescription.id))
        .join(Visit, Prescription.visit_id == Visit.id)
        .filter(or_(Prescription.custom_drug_name.is_(None), Prescription.custom_drug_name == ''))
    )
    if doctor_id is not None:
        query = query.filter(Visit.doctor_id == doctor_id)
    query = query.group_by(Prescription.brand_medication_id)
    return {brand_id: count for brand_id, count in query.all()}


def get_custom_prescription_counts(doctor_id=None):
    """Count prescriptions entered manually (not in the medication database)."""
    from sqlalchemy import func
    from models import db, Prescription, Visit

    query = (
        db.session.query(Prescription.custom_drug_name, func.count(Prescription.id))
        .join(Visit, Prescription.visit_id == Visit.id)
        .filter(Prescription.custom_drug_name.isnot(None), Prescription.custom_drug_name != '')
    )
    if doctor_id is not None:
        query = query.filter(Visit.doctor_id == doctor_id)
    query = query.group_by(Prescription.custom_drug_name)
    return {name: count for name, count in query.all()}


def build_prescription_stats(generic_drugs, brand_counts, custom_counts):
    """Build summary stats and sorted lists for the medications UI."""
    listed_rows = []
    total_listed = 0
    for drug in generic_drugs:
        for brand in drug.brands:
            if brand.brand_name == 'Manual Entry':
                continue
            count = brand_counts.get(brand.id, 0)
            total_listed += count
            listed_rows.append({
                'display': format_brand_label(brand),
                'generic_name': drug.generic_name,
                'brand_name': brand.brand_name,
                'formulation': brand.formulation or '',
                'count': count,
            })

    listed_rows.sort(key=lambda row: (-row['count'], row['display'].lower()))
    custom_rows = [
        {'name': name, 'count': count}
        for name, count in custom_counts.items()
    ]
    custom_rows.sort(key=lambda row: (-row['count'], row['name'].lower()))
    total_custom = sum(custom_counts.values())

    return {
        'total_listed': total_listed,
        'total_custom': total_custom,
        'total_prescriptions': total_listed + total_custom,
        'brands_prescribed': sum(1 for row in listed_rows if row['count'] > 0),
        'custom_drugs_prescribed': len(custom_rows),
        'listed_rows': listed_rows,
        'custom_rows': custom_rows,
    }
