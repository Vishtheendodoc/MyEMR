"""Clinic letterhead, price list, and pharmacy stock."""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import ClinicProfile, PriceItem, StockBatch
from app.services.clinic_scope import clinic_id_of

router = APIRouter(prefix="/clinic", tags=["clinic"])

DEFAULT_PRICES = [
    ("service", "Consultation — New patient", "999312", 800, 0, None),
    ("service", "Consultation — Follow-up", "999312", 500, 0, None),
    ("service", "HbA1c test", "999316", 400, 0, None),
    ("service", "Lipid profile", "999316", 600, 0, None),
    ("service", "Thyroid profile (TSH, FT4)", "999316", 700, 0, None),
    ("panel", "Diabetes panel", "999316", 1500, 0, "HbA1c\nLipid profile\nCreatinine"),
    ("panel", "Thyroid panel", "999316", 900, 0, "TSH\nFree T4"),
]


class ClinicProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str | None = None
    phone: str | None = None
    gstin: str | None = None
    signatory: str | None = None
    signature_data: str | None = None


class ClinicProfileOut(ClinicProfileIn):
    clinic_id: int
    state_code: str | None = None
    drug_licence: str | None = None
    pharmacy_name: str | None = None
    tax_mode: str | None = None


class PriceIn(BaseModel):
    kind: str = "service"
    name: str = Field(min_length=1, max_length=200)
    code: str | None = None
    rate: float = Field(default=0, ge=0)
    gst_percent: float = Field(default=0, ge=0, le=28)
    detail: str | None = None
    active: bool = True


class PriceOut(PriceIn):
    id: int


class StockIn(BaseModel):
    item_name: str = Field(min_length=1, max_length=200)
    batch_no: str | None = None
    expiry_date: date | None = None
    quantity: float = Field(gt=0)
    reorder_level: float = Field(default=10, ge=0)


class StockAdjust(BaseModel):
    quantity: float = Field(gt=0)
    batch_id: int | None = None
    batch_no: str | None = None
    expiry_date: date | None = None
    reason: str | None = None  # return | receive | writeoff | supplier


SYNTHETIC_BATCHES = {"RETURN", "RESTORE", "ADJUST"}


def _require_editor(user):
    if user.role not in {"doctor", "pharmacy", "billing"}:
        raise HTTPException(status_code=403, detail="This desk cannot change clinic setup")


def _require_pharmacy(user):
    if user.role not in {"doctor", "pharmacy"}:
        raise HTTPException(status_code=403, detail="Only pharmacy can change stock")


def _is_synthetic(batch_no: str | None) -> bool:
    return (batch_no or "").strip().upper() in SYNTHETIC_BATCHES


def _normalize_med(name: str) -> str:
    """Strip form/strength noise so 'Tab Glycomet GP 2 2/500 mg' ≈ 'glycomet gp 2'."""
    s = (name or "").lower()
    s = re.sub(r"\b(tab|tabs|tablet|tablets|cap|caps|capsule|capsules|inj|injection|syrup|susp|suspension)\b\.?", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\s*(mg|mcg|g|iu|ml|%|units?)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _med_tokens(name: str) -> set[str]:
    return {t for t in _normalize_med(name).split() if len(t) > 1 or t.isdigit()}


def resolve_stock_item_name(db: Session, clinic_id: int, label: str) -> str | None:
    """Map a dispense/Rx label to the clinic's stocked item_name (fuzzy)."""
    name = (label or "").strip()
    if not name:
        return None
    stocked = [
        r[0]
        for r in db.query(StockBatch.item_name)
        .filter(StockBatch.clinic_id == clinic_id)
        .distinct()
        .all()
        if r[0]
    ]
    if not stocked:
        return None
    lower = name.lower()
    for item in stocked:
        if item.lower() == lower:
            return item
    for item in stocked:
        il = item.lower()
        if lower in il or il in lower:
            return item
    norm = _normalize_med(name)
    if norm:
        for item in stocked:
            inn = _normalize_med(item)
            if inn and (inn == norm or inn in norm or norm in inn):
                return item
    tokens = _med_tokens(name)
    if not tokens:
        return None
    best_name = None
    best_score = 0.0
    for item in stocked:
        item_tokens = _med_tokens(item)
        if not item_tokens:
            continue
        overlap = len(tokens & item_tokens)
        if overlap == 0:
            continue
        # Prefer when stocked name is fully covered by the bill label
        coverage = overlap / len(item_tokens)
        if item_tokens <= tokens:
            coverage = max(coverage, 0.99)
        if coverage >= 0.6 and overlap >= min(2, len(item_tokens)) and coverage > best_score:
            best_score = coverage
            best_name = item
    return best_name


def _stock_rows_for_label(db: Session, clinic_id: int, label: str) -> tuple[str | None, list[StockBatch]]:
    resolved = resolve_stock_item_name(db, clinic_id, label)
    if not resolved:
        # Fall back to exact match (case-insensitive) for brand-new names
        rows = (
            db.query(StockBatch)
            .filter(StockBatch.clinic_id == clinic_id, StockBatch.item_name.ilike((label or "").strip()))
            .order_by(StockBatch.expiry_date.asc(), StockBatch.id.asc())
            .all()
        )
        return ((label or "").strip() or None, rows) if rows else (None, [])
    rows = (
        db.query(StockBatch)
        .filter(StockBatch.clinic_id == clinic_id, StockBatch.item_name == resolved)
        .order_by(StockBatch.expiry_date.asc(), StockBatch.id.asc())
        .all()
    )
    return resolved, rows


def _pick_credit_batch(
    db: Session,
    clinic_id: int,
    name: str,
    batch_id: int | None = None,
    batch_no: str | None = None,
    stock_status: str = "saleable",
):
    resolved, rows = _stock_rows_for_label(db, clinic_id, name)
    rows = [row for row in rows if (row.stock_status or "saleable") == stock_status]
    if batch_id:
        row = (
            db.query(StockBatch)
            .filter(StockBatch.id == batch_id, StockBatch.clinic_id == clinic_id)
            .first()
        )
        if row and (row.stock_status or "saleable") == stock_status:
            return row
    if batch_no and not _is_synthetic(batch_no) and rows:
        match = next((b for b in reversed(rows) if (b.batch_no or "").strip() == batch_no.strip()), None)
        if match:
            return match
    if not rows:
        return None
    today = date.today()
    usable = [
        b for b in rows
        if not _is_synthetic(b.batch_no)
        and (b.expiry_date is None or b.expiry_date >= today)
    ]
    if usable:
        with_qty = [b for b in usable if float(b.quantity or 0) > 0]
        return with_qty[0] if with_qty else usable[0]
    real = [b for b in rows if not _is_synthetic(b.batch_no)]
    return real[0] if real else rows[0]


def credit_stock(
    db: Session,
    clinic_id: int,
    item_name: str,
    quantity: float,
    *,
    batch_id: int | None = None,
    batch_no: str | None = None,
    expiry_date: date | None = None,
    reorder_level: float | None = None,
    txn_type: str = "stock_in",
    reason: str = "",
    reference_type: str | None = None,
    reference_id: str | None = None,
    user_id: int | None = None,
    stock_status: str = "saleable",
    medicine_id: int | None = None,
    supplier_id: int | None = None,
    purchase_rate: float | None = None,
    mrp: float | None = None,
    selling_price: float | None = None,
    gst_percent: float | None = None,
) -> StockBatch:
    """Add quantity onto an existing real batch — never spawn RETURN/RESTORE spam rows."""
    from app.services.inventory_ledger import write_ledger

    name = (item_name or "").strip()
    if not name or quantity <= 0:
        raise HTTPException(status_code=400, detail="Enter a medicine and quantity")
    target = _pick_credit_batch(db, clinic_id, name, batch_id=batch_id, batch_no=batch_no, stock_status=stock_status)
    if target:
        previous = float(target.quantity or 0)
        target.quantity = round(previous + float(quantity), 2)
        if reorder_level is not None:
            target.reorder_level = reorder_level
        if expiry_date and not target.expiry_date:
            target.expiry_date = expiry_date
        if batch_no and not target.batch_no:
            target.batch_no = batch_no.strip()
        write_ledger(
            db, target, previous, txn_type,
            reason=reason or name, reference_type=reference_type, reference_id=reference_id, user_id=user_id,
        )
        return target
    row = StockBatch(
        clinic_id=clinic_id,
        item_name=name,
        batch_no=(batch_no.strip() if batch_no and not _is_synthetic(batch_no) else None),
        expiry_date=expiry_date,
        quantity=float(quantity),
        reorder_level=reorder_level if reorder_level is not None else 10,
        medicine_id=medicine_id,
        supplier_id=supplier_id,
        purchase_rate=purchase_rate,
        mrp=mrp,
        selling_price=selling_price,
        gst_percent=gst_percent or 0,
        stock_status=stock_status,
    )
    db.add(row)
    db.flush()
    write_ledger(
        db, row, 0, txn_type,
        reason=reason or name, reference_type=reference_type, reference_id=reference_id, user_id=user_id,
    )
    return row


def debit_stock(
    db: Session,
    clinic_id: int,
    item_name: str,
    quantity: float,
    *,
    batch_id: int | None = None,
    txn_type: str = "stock_out",
    reason: str = "",
    reference_type: str | None = None,
    reference_id: str | None = None,
    user_id: int | None = None,
) -> None:
    """Remove quantity (write-off / supplier return) from a specific or FEFO batch."""
    from app.services.inventory_ledger import write_ledger

    name = (item_name or "").strip()
    if not name or quantity <= 0:
        raise HTTPException(status_code=400, detail="Enter a medicine and quantity")
    today = date.today()
    if batch_id:
        batch = (
            db.query(StockBatch)
            .filter(StockBatch.id == batch_id, StockBatch.clinic_id == clinic_id)
            .first()
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        if float(batch.quantity or 0) + 1e-9 < quantity:
            raise HTTPException(status_code=400, detail="Not enough in that batch")
        previous = float(batch.quantity)
        batch.quantity = round(previous - float(quantity), 2)
        write_ledger(
            db, batch, previous, txn_type,
            reason=reason or name, reference_type=reference_type, reference_id=reference_id, user_id=user_id,
        )
        return
    _resolved, all_rows = _stock_rows_for_label(db, clinic_id, name)
    batches = [b for b in all_rows if float(b.quantity or 0) > 0 and (b.stock_status or "saleable") == "saleable"]
    usable = [b for b in batches if b.expiry_date is None or b.expiry_date >= today] or batches
    remaining = float(quantity)
    for batch in usable:
        previous = float(batch.quantity)
        take = min(previous, remaining)
        batch.quantity = round(previous - take, 2)
        write_ledger(
            db, batch, previous, txn_type,
            reason=reason or name, reference_type=reference_type, reference_id=reference_id, user_id=user_id,
        )
        remaining = round(remaining - take, 2)
        if remaining <= 0:
            return
    raise HTTPException(status_code=400, detail=f"Not enough stock for {name}. Short by {remaining}.")


def consolidate_item_batches(db: Session, clinic_id: int, item_name: str) -> StockBatch | None:
    """Fold RETURN/RESTORE/zero rows into one real batch and delete empties."""
    name = item_name.strip()
    rows = (
        db.query(StockBatch)
        .filter(StockBatch.clinic_id == clinic_id, StockBatch.item_name.ilike(name))
        .order_by(StockBatch.id.asc())
        .all()
    )
    if not rows:
        return None
    primary = next((b for b in rows if not _is_synthetic(b.batch_no)), rows[0])
    if _is_synthetic(primary.batch_no):
        primary.batch_no = None
    total = round(sum(float(b.quantity or 0) for b in rows), 2)
    reorder = min(float(b.reorder_level or 10) for b in rows)
    expiry = next((b.expiry_date for b in rows if b.expiry_date and not _is_synthetic(b.batch_no)), None)
    batch_no = next((b.batch_no for b in rows if b.batch_no and not _is_synthetic(b.batch_no)), None)
    primary.quantity = total
    primary.reorder_level = reorder
    if expiry:
        primary.expiry_date = expiry
    if batch_no:
        primary.batch_no = batch_no
    for row in rows:
        if row.id == primary.id:
            continue
        db.delete(row)
    return primary


def _profile(db: Session, clinic_id: int) -> ClinicProfile:
    row = db.get(ClinicProfile, clinic_id)
    if row:
        return row
    row = ClinicProfile(clinic_id=clinic_id, name="Endo Clinic")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _seed_prices(db: Session, clinic_id: int) -> None:
    if db.query(PriceItem).filter(PriceItem.clinic_id == clinic_id).count():
        return
    for kind, name, code, rate, gst, detail in DEFAULT_PRICES:
        db.add(PriceItem(
            clinic_id=clinic_id, kind=kind, name=name, code=code,
            rate=rate, gst_percent=gst, detail=detail, active=True,
        ))
    db.commit()


def letterhead(db: Session, clinic_id: int) -> dict:
    row = _profile(db, clinic_id)
    return {
        "clinic_id": row.clinic_id,
        "name": row.name,
        "address": row.address,
        "phone": row.phone,
        "gstin": row.gstin,
        "signatory": row.signatory,
        "signature_data": row.signature_data,
        "state_code": row.state_code,
        "drug_licence": row.drug_licence,
        "pharmacy_name": row.pharmacy_name,
        "tax_mode": row.tax_mode,
    }


def _batch_stamp(batch, quantity: float) -> dict:
    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
        "mrp": batch.mrp,
        "quantity": quantity,
    }


def consume_stock(db: Session, clinic_id: int, item_name: str, quantity: float, batch_id: int | None = None) -> list[dict]:
    """Reduce FEFO stock for a dispensed medicine. A chosen batch is locked on that line."""
    from app.services.inventory_ledger import write_ledger

    name = (item_name or "").strip()
    if not name or quantity <= 0:
        return []
    resolved, all_rows = _stock_rows_for_label(db, clinic_id, name)
    if batch_id:
        batch = db.get(StockBatch, int(batch_id))
        if not batch or batch.clinic_id != clinic_id:
            raise HTTPException(status_code=400, detail="That batch is not in this clinic")
        if (batch.stock_status or "saleable") != "saleable":
            raise HTTPException(status_code=400, detail="That batch is not saleable")
        if batch.expiry_date and batch.expiry_date < date.today():
            raise HTTPException(status_code=400, detail=f"Expired stock cannot be dispensed for {batch.item_name}.")
        if float(batch.quantity or 0) + 0.001 < float(quantity):
            raise HTTPException(status_code=400, detail=f"Not enough stock in batch {batch.batch_no or batch.id}.")
        previous = float(batch.quantity)
        batch.quantity = round(previous - float(quantity), 2)
        write_ledger(db, batch, previous, "sale", reason=name, reference_type="dispense")
        return [_batch_stamp(batch, float(quantity))]
    if not resolved or not all_rows:
        return []
    today = date.today()
    tracked = [b for b in all_rows if float(b.quantity or 0) > 0 and (b.stock_status or "saleable") == "saleable"]
    usable = [b for b in tracked if b.expiry_date is None or b.expiry_date >= today]
    expired = [b for b in tracked if b not in usable]
    remaining = float(quantity)
    used: list[dict] = []
    for batch in usable:
        previous = float(batch.quantity)
        take = min(previous, remaining)
        batch.quantity = round(previous - take, 2)
        write_ledger(db, batch, previous, "sale", reason=name, reference_type="dispense")
        used.append(_batch_stamp(batch, take))
        remaining = round(remaining - take, 2)
        if remaining <= 0:
            return used
    if remaining > 0 and expired and not usable:
        raise HTTPException(status_code=400, detail=f"Expired stock cannot be dispensed for {resolved}.")
    if remaining > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough stock for {resolved} (from “{name}”). Short by {remaining}.",
        )
    return used


def consume_lines(db: Session, clinic_id: int, lines: list[dict]) -> None:
    for line in lines:
        code = str(line.get("procedure_code") or "")
        if code != "300490":
            continue
        taken = consume_stock(
            db, clinic_id, line.get("description") or "", float(line.get("quantity") or 1), line.get("batch_id"),
        )
        if not taken:
            continue
        line["batch_no"] = ", ".join(item["batch_no"] for item in taken if item.get("batch_no")) or None
        line["expiry_date"] = taken[0].get("expiry_date")
        line["mrp"] = taken[0].get("mrp")
        line["batches"] = taken


def restore_stock(db: Session, clinic_id: int, item_name: str, quantity: float) -> None:
    name = (item_name or "").strip()
    if not name or quantity <= 0:
        return
    resolved, rows = _stock_rows_for_label(db, clinic_id, name)
    if not resolved and not rows:
        return
    credit_stock(db, clinic_id, resolved or name, float(quantity))


def restore_lines(db: Session, clinic_id: int, lines: list[dict]) -> None:
    for line in lines:
        if str(line.get("procedure_code") or "") != "300490":
            continue
        restore_stock(db, clinic_id, line.get("description") or "", float(line.get("quantity") or 1))


@router.get("/profile", response_model=ClinicProfileOut)
def get_profile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return letterhead(db, clinic_id_of(user))


@router.put("/profile", response_model=ClinicProfileOut)
def save_profile(data: ClinicProfileIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only the doctor can edit the letterhead")
    if data.signature_data and len(data.signature_data) > 300_000:
        raise HTTPException(status_code=400, detail="Signature image is too large")
    row = _profile(db, clinic_id_of(user))
    for key, value in data.model_dump().items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(row)
    return letterhead(db, row.clinic_id)


@router.get("/prices", response_model=list[PriceOut])
def list_prices(user=Depends(get_current_user), db: Session = Depends(get_db)):
    clinic_id = clinic_id_of(user)
    _seed_prices(db, clinic_id)
    rows = (
        db.query(PriceItem)
        .filter(PriceItem.clinic_id == clinic_id, PriceItem.active.is_(True))
        .order_by(PriceItem.kind, PriceItem.name)
        .all()
    )
    return rows


@router.post("/prices", response_model=PriceOut, status_code=201)
def create_price(data: PriceIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_editor(user)
    if data.kind not in {"service", "panel", "favorite", "medicine"}:
        raise HTTPException(status_code=400, detail="Unknown price type")
    row = PriceItem(clinic_id=clinic_id_of(user), **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/prices/{item_id}", response_model=PriceOut)
def update_price(item_id: int, data: PriceIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_editor(user)
    row = db.get(PriceItem, item_id)
    if not row or row.clinic_id != clinic_id_of(user):
        raise HTTPException(status_code=404, detail="Price not found")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/prices/{item_id}", status_code=204)
def delete_price(item_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_editor(user)
    row = db.get(PriceItem, item_id)
    if not row or row.clinic_id != clinic_id_of(user):
        raise HTTPException(status_code=404, detail="Price not found")
    row.active = False
    db.commit()


@router.get("/stock")
def list_stock(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(StockBatch)
        .filter(StockBatch.clinic_id == clinic_id_of(user))
        .order_by(StockBatch.item_name, StockBatch.expiry_date)
        .all()
    )
    today = date.today()
    grouped: dict[str, dict] = {}
    for row in rows:
        bucket = grouped.setdefault(row.item_name, {
            "item_name": row.item_name,
            "quantity": 0,
            "reorder_level": row.reorder_level,
            "batches": [],
            "messy": False,
        })
        bucket["quantity"] = round(float(bucket["quantity"]) + float(row.quantity or 0), 2)
        bucket["reorder_level"] = min(float(bucket["reorder_level"] or 10), float(row.reorder_level or 10))
        if _is_synthetic(row.batch_no):
            bucket["messy"] = True
        # Hide emptied synthetic rows from the desk view
        if float(row.quantity or 0) <= 0 and _is_synthetic(row.batch_no):
            continue
        bucket["batches"].append({
            "id": row.id,
            "batch_no": None if _is_synthetic(row.batch_no) else row.batch_no,
            "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
            "quantity": row.quantity,
            "expired": bool(row.expiry_date and row.expiry_date < today),
            "synthetic": _is_synthetic(row.batch_no),
        })
    items = []
    for bucket in grouped.values():
        if float(bucket["quantity"]) <= 0 and not bucket["batches"]:
            continue
        bucket["low"] = bucket["quantity"] <= bucket["reorder_level"]
        items.append(bucket)
    return sorted(items, key=lambda x: x["item_name"].lower())


@router.post("/stock", status_code=201)
def add_stock(data: StockIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_pharmacy(user)
    # Same batch number → top up; otherwise create a new batch line
    clinic_id = clinic_id_of(user)
    existing = None
    if data.batch_no:
        existing = (
            db.query(StockBatch)
            .filter(
                StockBatch.clinic_id == clinic_id,
                StockBatch.item_name.ilike(data.item_name.strip()),
                StockBatch.batch_no == data.batch_no.strip(),
            )
            .first()
        )
    if existing:
        existing.quantity = round(float(existing.quantity or 0) + float(data.quantity), 2)
        existing.reorder_level = data.reorder_level
        if data.expiry_date:
            existing.expiry_date = data.expiry_date
        db.commit()
        return {"id": existing.id}
    row = StockBatch(clinic_id=clinic_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.post("/stock/return/{item_name}", status_code=201)
def return_named_stock(item_name: str, data: StockAdjust, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Patient return / credit — adds qty back onto an existing batch (no new RETURN rows)."""
    _require_pharmacy(user)
    row = credit_stock(
        db,
        clinic_id_of(user),
        item_name,
        data.quantity,
        batch_id=data.batch_id,
        batch_no=data.batch_no,
        expiry_date=data.expiry_date,
    )
    db.commit()
    db.refresh(row)
    return {"id": row.id, "batch_no": row.batch_no, "quantity": row.quantity}


@router.post("/stock/writeoff/{item_name}", status_code=201)
def writeoff_stock(item_name: str, data: StockAdjust, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Supplier return or damage write-off — subtracts from stock."""
    _require_pharmacy(user)
    debit_stock(db, clinic_id_of(user), item_name, data.quantity, batch_id=data.batch_id)
    db.commit()
    return {"success": True}


@router.post("/stock/consolidate")
def consolidate_stock(
    item_name: str | None = Query(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge RETURN/RESTORE spam and empty rows into clean batches."""
    _require_pharmacy(user)
    clinic_id = clinic_id_of(user)
    if item_name:
        names = [item_name.strip()]
    else:
        names = [
            r[0]
            for r in db.query(StockBatch.item_name)
            .filter(StockBatch.clinic_id == clinic_id)
            .distinct()
            .all()
        ]
    fixed = 0
    for name in names:
        rows = (
            db.query(StockBatch)
            .filter(StockBatch.clinic_id == clinic_id, StockBatch.item_name.ilike(name))
            .all()
        )
        if len(rows) <= 1 and not any(_is_synthetic(r.batch_no) for r in rows):
            # Still drop empty synthetic singles
            if len(rows) == 1 and _is_synthetic(rows[0].batch_no) and float(rows[0].quantity or 0) <= 0:
                db.delete(rows[0])
                fixed += 1
            continue
        consolidate_item_batches(db, clinic_id, name)
        fixed += 1
    db.commit()
    return {"success": True, "items_cleaned": fixed}
