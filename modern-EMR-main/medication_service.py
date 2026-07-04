"""Medication upload helpers and database normalization."""

import os
import re

import pandas as pd

from models import db, GenericDrug, BrandMedication

RANGE_STRENGTH_RE = re.compile(r'\d+\.?\d*\s*-\s*\d+\.?\d*')

SEMAGLUTIDE_5_STRENGTHS = ['0.25mg', '0.5mg', '1mg', '1.7mg', '2.4mg']
OZEMPIC_STRENGTHS = ['0.25mg', '0.5mg', '1mg', '2mg']
SEMATRINITY_STRENGTHS = ['2mg', '4mg']

MANUAL_ENTRY_BRAND = 'manual entry'


def is_range_strength(strength):
    return bool(RANGE_STRENGTH_RE.search((strength or '').strip()))


def normalize_strength(strength):
    return re.sub(r'\s+', '', (strength or '').strip().lower())


def brand_strength_key(brand_name, strength):
    return (brand_name.strip().lower(), normalize_strength(strength))


def strengths_for_semaglutide_brand(brand_name, strength):
    name = (brand_name or '').strip()
    strength_lower = (strength or '').lower()
    if name == 'Ozempic':
        return list(OZEMPIC_STRENGTHS)
    if name == 'Sematrinity' or ('2-4' in strength_lower and '0.25' not in strength_lower):
        return list(SEMATRINITY_STRENGTHS)
    return list(SEMAGLUTIDE_5_STRENGTHS)


def is_protected_brand(brand):
    return (brand.brand_name or '').strip().lower() == MANUAL_ENTRY_BRAND


def find_brands_by_name_strength(brand_name, strength):
    target = brand_strength_key(brand_name, strength)
    matches = []
    for brand in BrandMedication.query.filter(
        db.func.lower(BrandMedication.brand_name) == brand_name.strip().lower()
    ).all():
        if brand_strength_key(brand.brand_name, brand.strength) == target:
            matches.append(brand)
    return matches


def merge_brand_duplicates(primary, duplicates):
    """Keep one brand row and move any prescriptions off duplicate rows."""
    from models import Prescription

    with db.session.no_autoflush:
        for duplicate in duplicates:
            if duplicate.id == primary.id:
                continue
            for prescription in Prescription.query.filter_by(brand_medication_id=duplicate.id).all():
                prescription.brand_medication_id = primary.id
            db.session.delete(duplicate)
    db.session.flush()


def split_semaglutide_range_brands():
    """Convert combined strengths (e.g. 0.25-2.4 mg) into individual brand rows."""
    generic = GenericDrug.query.filter_by(generic_name='Semaglutide').first()
    if not generic:
        return 0

    changed = 0
    range_brands = BrandMedication.query.filter_by(generic_drug_id=generic.id).all()
    for brand in range_brands:
        if not is_range_strength(brand.strength):
            continue

        strengths = strengths_for_semaglutide_brand(brand.brand_name, brand.strength)
        if not strengths:
            continue

        brand.strength = strengths[0]
        changed += 1

        for strength in strengths[1:]:
            exists = BrandMedication.query.filter_by(
                brand_name=brand.brand_name,
                generic_drug_id=generic.id,
                strength=strength,
            ).first()
            if exists:
                continue
            db.session.add(BrandMedication(
                brand_name=brand.brand_name,
                generic_drug_id=generic.id,
                manufacturer=brand.manufacturer,
                strength=strength,
                formulation=brand.formulation or 'Injection',
                price=brand.price,
            ))
            changed += 1

    if changed:
        db.session.commit()
    return changed


def upsert_brand_from_row(generic_drug, row):
    """Insert or update a brand using brand name + strength as the key."""
    brand_name = str(row['brand_name']).strip()
    strength = str(row.get('strength', '') or '').strip()

    manufacturer = str(row.get('manufacturer', '') or '').strip() or None
    formulation = str(row.get('formulation', '') or '').strip() or None
    price = row.get('price', None)
    try:
        price = float(price) if price not in (None, '', 'nan') else None
    except (TypeError, ValueError):
        price = None

    matches = find_brands_by_name_strength(brand_name, strength)
    if matches:
        primary = matches[0]
        primary.generic_drug_id = generic_drug.id
        if manufacturer:
            primary.manufacturer = manufacturer
        if formulation:
            primary.formulation = formulation
        if price is not None:
            primary.price = price
        if len(matches) > 1:
            merge_brand_duplicates(primary, matches[1:])
        return False

    db.session.add(BrandMedication(
        brand_name=brand_name,
        generic_drug_id=generic_drug.id,
        manufacturer=manufacturer,
        strength=strength,
        formulation=formulation,
        price=price,
    ))
    return True


def prune_stale_brands(uploaded_keys):
    """Remove obsolete brand rows that are not in the formulary and have no prescriptions."""
    from models import Prescription

    removed = 0
    for brand in BrandMedication.query.all():
        if is_protected_brand(brand):
            continue
        key = brand_strength_key(brand.brand_name, brand.strength)
        if key in uploaded_keys:
            continue
        if Prescription.query.filter_by(brand_medication_id=brand.id).first():
            continue
        db.session.delete(brand)
        removed += 1
    return removed


def process_medication_rows(rows):
    """Apply formulary rows to the database and prune obsolete brand entries."""
    generic_count = 0
    brand_count = 0
    uploaded_keys = set()

    for row in rows:
        generic_name = str(row.get('generic_name', '')).strip()
        brand_name = str(row.get('brand_name', '')).strip()
        if not generic_name or not brand_name:
            continue

        uploaded_keys.add(brand_strength_key(brand_name, row.get('strength', '')))

        generic_drug = GenericDrug.query.filter_by(generic_name=generic_name).first()
        if not generic_drug:
            generic_drug = GenericDrug(
                generic_name=generic_name,
                drug_class=row.get('drug_class', ''),
                indication=row.get('indication', ''),
            )
            db.session.add(generic_drug)
            db.session.flush()
            generic_count += 1
        else:
            drug_class = str(row.get('drug_class', '') or '').strip()
            indication = str(row.get('indication', '') or '').strip()
            if drug_class:
                generic_drug.drug_class = drug_class
            if indication:
                generic_drug.indication = indication

        if upsert_brand_from_row(generic_drug, row):
            brand_count += 1

    db.session.flush()
    removed_count = prune_stale_brands(uploaded_keys)
    db.session.commit()
    split_semaglutide_range_brands()
    return {
        'generic_count': generic_count,
        'brand_count': brand_count,
        'removed_count': removed_count,
    }


def sync_medication_template():
    """Sync the master CSV formulary into the database on startup."""
    basedir = os.path.abspath(os.path.dirname(__file__))
    csv_path = os.path.join(basedir, 'medication_template.csv')
    if not os.path.exists(csv_path):
        return None

    df = pd.read_csv(csv_path)
    return process_medication_rows(df.to_dict('records'))
