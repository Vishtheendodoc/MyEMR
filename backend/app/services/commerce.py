"""Purchases, returns, payments, and finance totals.

Stock quantities change only through the pharmacy stock helpers, which write the inventory ledger.
Original invoices are not deleted. A return is a new document.
GST amounts are split for the clinic invoice. This is bookkeeping, not a filed GST return.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Bill,
    BillPayment,
    ClinicProfile,
    InventoryTxn,
    MedicineItem,
    Patient,
    PatientAdvance,
    Prescription,
    PurchaseInvoice,
    PurchaseLine,
    PurchaseReturn,
    PurchaseReturnLine,
    SalesReturn,
    SalesReturnLine,
    StockBatch,
    Supplier,
    TaxNote,
)
from app.services.invoice_series import STATE_CODES, next_document_number, rupee_round
from app.services.clinic_scope import clinic_id_of, owning_doctor_id
from app.services.clinic_time import clinic_day, clinic_period_utc
from app.services.opd_visit import ensure_opd_visit_for_day


def to_base_units(quantity: float, unit: str, pack_size: float, strip_size: float) -> float:
    unit_name = (unit or "tablet").strip().lower()
    pack = pack_size if pack_size and pack_size > 0 else 1
    strip = strip_size if strip_size and strip_size > 0 else 1
    if unit_name in {"box", "pack"}:
        return round(quantity * pack * strip, 2)
    if unit_name == "strip":
        return round(quantity * strip, 2)
    return round(quantity, 2)


def apply_tax_split(db: Session, user, bill: Bill) -> None:
    profile = db.get(ClinicProfile, clinic_id_of(user))
    tax = round(float(bill.gst_amount or 0), 2)
    mode = (profile.tax_mode if profile and profile.tax_mode else "split").lower()
    home = (profile.state_code if profile and profile.state_code else "").strip()
    supply = (bill.place_of_supply or home).strip()
    if tax <= 0 or mode == "none":
        bill.cgst_amount = 0
        bill.sgst_amount = 0
        bill.igst_amount = 0
        return
    if mode == "igst" or (home and supply and supply != home):
        bill.cgst_amount = 0
        bill.sgst_amount = 0
        bill.igst_amount = tax
        return
    half = round(tax / 2, 2)
    bill.cgst_amount = half
    bill.sgst_amount = round(tax - half, 2)
    bill.igst_amount = 0


def annotate_bill(db: Session, user, bill: Bill) -> None:
    mapping = {"pharmacy": "medicine", "lab": "investigation", "visit": "consultation"}
    if not bill.bill_type:
        bill.bill_type = mapping.get((bill.category or "").lower(), bill.category or "other")
    apply_tax_split(db, user, bill)


def clinic_id_of_bill(db: Session, bill: Bill) -> int:
    patient = db.get(Patient, bill.patient_id)
    return patient.clinic_id if patient else 1


def record_payment(
    db: Session,
    bill: Bill,
    amount: float,
    method: str | None,
    user_id: int | None,
    *,
    kind: str = "collection",
    note: str | None = None,
) -> BillPayment | None:
    value = round(float(amount or 0), 2)
    if abs(value) < 0.009:
        return None
    if bill.id is None:
        db.flush()
    row = BillPayment(
        bill_id=bill.id,
        clinic_id=clinic_id_of_bill(db, bill),
        amount=value,
        method=(method or "Cash").strip() or "Cash",
        kind=kind,
        note=note,
        user_id=user_id,
    )
    db.add(row)
    db.flush()
    return row


def record_dispensed(db: Session, visit_id: int, lines: list[dict]) -> None:
    rows = db.query(Prescription).filter_by(visit_id=visit_id).all()
    for line in lines:
        if str(line.get("procedure_code") or "") != "300490":
            continue
        label = (line.get("description") or "").strip().lower()
        qty = float(line.get("quantity") or 0)
        if not label or qty <= 0:
            continue
        match = next((
            rx for rx in rows
            if (rx.custom_drug_name or "").lower() and (rx.custom_drug_name or "").lower() in label
        ), None)
        if match is None:
            match = next((
                rx for rx in rows
                if rx.brand_medication and rx.brand_medication.brand_name.lower() in label
            ), None)
        if match is None:
            continue
        match.dispensed_quantity = round(float(match.dispensed_quantity or 0) + qty, 2)


def _next_doc(db: Session, clinic_id: int, model, column: str, prefix: str) -> str:
    return next_document_number(db, clinic_id, prefix)


def medicine_dict(row: MedicineItem) -> dict:
    return {
        "id": row.id,
        "brand_name": row.brand_name,
        "generic_name": row.generic_name,
        "composition": row.composition,
        "strength": row.strength,
        "dosage_form": row.dosage_form,
        "manufacturer": row.manufacturer,
        "category": row.category,
        "schedule": row.schedule,
        "hsn_code": row.hsn_code,
        "gst_percent": row.gst_percent or 0,
        "purchase_price": row.purchase_price,
        "mrp": row.mrp,
        "selling_price": row.selling_price,
        "barcode": row.barcode,
        "min_stock": row.min_stock or 0,
        "reorder_level": row.reorder_level or 0,
        "base_unit": row.base_unit,
        "pack_size": row.pack_size or 1,
        "strip_size": row.strip_size or 1,
        "active": bool(row.active),
    }


def save_medicine(db: Session, clinic_id: int, data: dict) -> MedicineItem:
    name = (data.get("brand_name") or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Enter the medicine name")
    row = MedicineItem(
        clinic_id=clinic_id,
        brand_name=name,
        generic_name=(data.get("generic_name") or "").strip() or None,
        composition=(data.get("composition") or "").strip() or None,
        strength=(data.get("strength") or "").strip() or None,
        dosage_form=(data.get("dosage_form") or "tablet").strip(),
        manufacturer=(data.get("manufacturer") or "").strip() or None,
        category=(data.get("category") or "").strip() or None,
        schedule=(data.get("schedule") or "").strip() or None,
        hsn_code=(data.get("hsn_code") or "300490").strip(),
        gst_percent=float(data.get("gst_percent") or 0),
        purchase_price=data.get("purchase_price"),
        mrp=data.get("mrp"),
        selling_price=data.get("selling_price"),
        barcode=(data.get("barcode") or "").strip() or None,
        min_stock=float(data.get("min_stock") or 0),
        reorder_level=float(data.get("reorder_level") or 10),
        base_unit=(data.get("base_unit") or "tablet").strip(),
        pack_size=float(data.get("pack_size") or 1),
        strip_size=float(data.get("strip_size") or 1),
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def search_medicines(db: Session, clinic_id: int, query: str) -> list[MedicineItem]:
    rows = db.query(MedicineItem).filter(MedicineItem.clinic_id == clinic_id, MedicineItem.active.is_(True))
    text = (query or "").strip()
    if text:
        like = f"%{text}%"
        rows = rows.filter(
            MedicineItem.brand_name.ilike(like)
            | MedicineItem.generic_name.ilike(like)
            | MedicineItem.composition.ilike(like)
            | MedicineItem.manufacturer.ilike(like)
            | MedicineItem.barcode.ilike(like)
        )
    return rows.order_by(MedicineItem.brand_name.asc()).limit(40).all()


def save_supplier(db: Session, clinic_id: int, data: dict) -> Supplier:
    name = (data.get("name") or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Enter the supplier name")
    row = Supplier(
        clinic_id=clinic_id,
        name=name,
        gstin=(data.get("gstin") or "").strip() or None,
        drug_licence=(data.get("drug_licence") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
        payment_terms=(data.get("payment_terms") or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def confirm_purchase(db: Session, user, data: dict) -> PurchaseInvoice:
    from app.api.v1.clinic_admin import credit_stock

    clinic_id = clinic_id_of(user)
    supplier = db.get(Supplier, int(data["supplier_id"]))
    if not supplier or supplier.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="Supplier not found")
    invoice_no = (data.get("supplier_invoice_no") or "").strip()
    if not invoice_no:
        raise HTTPException(status_code=400, detail="Enter the supplier invoice number")
    duplicate = (
        db.query(PurchaseInvoice)
        .filter_by(clinic_id=clinic_id, supplier_id=supplier.id, supplier_invoice_no=invoice_no)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail=f"Supplier invoice {invoice_no} is already entered")
    lines = data.get("lines") or []
    if not lines:
        raise HTTPException(status_code=400, detail="Add at least one medicine")
    try:
        invoice_date = date.fromisoformat(str(data.get("invoice_date") or date.today().isoformat()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invoice date must be YYYY-MM-DD") from exc
    purchase = PurchaseInvoice(
        clinic_id=clinic_id,
        supplier_id=supplier.id,
        document_no=_next_doc(db, clinic_id, PurchaseInvoice, "document_no", "PUR"),
        supplier_invoice_no=invoice_no,
        invoice_date=invoice_date,
        created_by=user.id,
    )
    db.add(purchase)
    db.flush()
    total = 0.0
    gst_total = 0.0
    for raw in lines:
        medicine = db.get(MedicineItem, int(raw["medicine_id"])) if raw.get("medicine_id") else None
        name = (raw.get("medicine_name") or (medicine.brand_name if medicine else "")).strip()
        if not name:
            raise HTTPException(status_code=400, detail="Each purchase line needs a medicine")
        pack = float(raw.get("pack_size") or (medicine.pack_size if medicine else 1) or 1)
        strip = float(raw.get("strip_size") or (medicine.strip_size if medicine else 1) or 1)
        unit = raw.get("unit") or (medicine.base_unit if medicine else "tablet") or "tablet"
        qty = float(raw.get("quantity") or 0)
        free = float(raw.get("free_quantity") or 0)
        if qty <= 0 and free <= 0:
            raise HTTPException(status_code=400, detail=f"Enter a quantity for {name}")
        base_qty = to_base_units(qty + free, unit, pack, strip)
        rate = float(raw.get("purchase_rate") or 0)
        gst_percent = float(raw["gst_percent"]) if raw.get("gst_percent") is not None else float(medicine.gst_percent if medicine else 0)
        line_base = round(qty * rate, 2)
        gst = round(line_base * gst_percent / 100, 2)
        line_total = round(line_base + gst, 2)
        expiry = date.fromisoformat(str(raw["expiry_date"])) if raw.get("expiry_date") else None
        batch = credit_stock(
            db, clinic_id, name, base_qty,
            batch_no=(raw.get("batch_no") or "").strip() or None,
            expiry_date=expiry,
            txn_type="purchase",
            reason=f"Purchase {purchase.document_no}",
            reference_type="purchase",
            reference_id=str(purchase.id),
            user_id=user.id,
            medicine_id=medicine.id if medicine else None,
            supplier_id=supplier.id,
            purchase_rate=rate,
            mrp=raw.get("mrp"),
            selling_price=raw.get("selling_price"),
            gst_percent=gst_percent,
        )
        db.add(PurchaseLine(
            purchase_id=purchase.id,
            medicine_id=medicine.id if medicine else None,
            medicine_name=name,
            batch_no=batch.batch_no,
            expiry_date=expiry,
            quantity=qty,
            unit=unit,
            free_quantity=free,
            base_quantity=base_qty,
            purchase_rate=rate,
            mrp=raw.get("mrp"),
            selling_price=raw.get("selling_price"),
            gst_percent=gst_percent,
            line_total=line_total,
            batch_id=batch.id,
        ))
        total += line_total
        gst_total += gst
    purchase.amount = round(total, 2)
    purchase.gst_amount = round(gst_total, 2)
    db.commit()
    db.refresh(purchase)
    return purchase


def purchase_dict(db: Session, row: PurchaseInvoice) -> dict:
    supplier = db.get(Supplier, row.supplier_id)
    lines = db.query(PurchaseLine).filter_by(purchase_id=row.id).all()
    return {
        "id": row.id,
        "document_no": row.document_no,
        "supplier_id": row.supplier_id,
        "supplier_name": supplier.name if supplier else "",
        "supplier_invoice_no": row.supplier_invoice_no,
        "invoice_date": row.invoice_date.isoformat(),
        "amount": row.amount or 0,
        "gst_amount": row.gst_amount or 0,
        "paid_amount": row.paid_amount or 0,
        "outstanding": round(max(float(row.amount or 0) - float(row.paid_amount or 0), 0), 2),
        "status": row.status,
        "lines": [
            {
                "id": line.id,
                "medicine_name": line.medicine_name,
                "batch_no": line.batch_no,
                "expiry_date": line.expiry_date.isoformat() if line.expiry_date else None,
                "quantity": line.quantity,
                "unit": line.unit,
                "base_quantity": line.base_quantity,
                "returned_base": line.returned_base or 0,
                "line_total": line.line_total or 0,
                "batch_id": line.batch_id,
            }
            for line in lines
        ],
    }


def pay_purchase(db: Session, user, purchase_id: int, amount: float) -> PurchaseInvoice:
    row = db.get(PurchaseInvoice, purchase_id)
    if not row or row.clinic_id != clinic_id_of(user):
        raise HTTPException(status_code=404, detail="Purchase not found")
    paying = round(float(amount or 0), 2)
    if paying <= 0:
        raise HTTPException(status_code=400, detail="Enter the amount paid to the supplier")
    row.paid_amount = round(float(row.paid_amount or 0) + paying, 2)
    db.commit()
    db.refresh(row)
    return row


def _lines(bill: Bill) -> list[dict]:
    if not bill.line_items:
        return []
    try:
        return json.loads(bill.line_items)
    except json.JSONDecodeError:
        return []


def sales_return(db: Session, user, data: dict) -> SalesReturn:
    from app.api.v1.clinic_admin import credit_stock

    clinic_id = clinic_id_of(user)
    invoice_no = (data.get("invoice_number") or "").strip()
    bill = (
        db.query(Bill)
        .join(Patient, Bill.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id, Bill.invoice_number == invoice_no)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Invoice not found")
    description = (data.get("description") or "").strip()
    qty = float(data.get("quantity") or 0)
    if not description or qty <= 0:
        raise HTTPException(status_code=400, detail="Enter the medicine and quantity being returned")
    condition = (data.get("condition") or "saleable").strip().lower()
    if condition not in {"saleable", "damaged"}:
        raise HTTPException(status_code=400, detail="Condition must be saleable or damaged")
    match = next((line for line in _lines(bill) if description.lower() in (line.get("description") or "").lower()), None)
    if not match:
        raise HTTPException(status_code=400, detail="That medicine is not on this invoice")
    sold = float(match.get("quantity") or 0)
    already = (
        db.query(SalesReturnLine)
        .join(SalesReturn, SalesReturnLine.sales_return_id == SalesReturn.id)
        .filter(SalesReturn.bill_id == bill.id, SalesReturnLine.description == (match.get("description") or description))
        .all()
    )
    returned = sum(float(line.quantity or 0) for line in already)
    if returned + qty > sold + 0.001:
        raise HTTPException(status_code=400, detail=f"Only {round(max(sold - returned, 0), 2)} can still be returned")
    rate = float(match.get("rate") or 0)
    gst = float(match.get("gst_percent") or 0)
    amount = round(qty * rate * (1 + gst / 100), 2)
    reason = (data.get("reason") or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=400, detail="Enter a reason for the return")
    document = SalesReturn(
        clinic_id=clinic_id,
        bill_id=bill.id,
        document_no=_next_doc(db, clinic_id, SalesReturn, "document_no", "CN"),
        amount=amount,
        reason=reason,
        condition=condition,
        created_by=user.id,
    )
    db.add(document)
    db.flush()
    batch_no = (data.get("batch_no") or match.get("batch_no") or "").strip() or None
    db.add(SalesReturnLine(
        sales_return_id=document.id,
        description=match.get("description") or description,
        batch_no=batch_no,
        quantity=qty,
        amount=amount,
    ))
    credit_stock(
        db, clinic_id, match.get("description") or description, qty,
        batch_no=batch_no,
        txn_type="sales_return" if condition == "saleable" else "quarantine",
        reason=reason,
        reference_type="sales_return",
        reference_id=str(document.id),
        user_id=user.id,
        stock_status="quarantine" if condition == "damaged" else "saleable",
    )
    if data.get("refund"):
        refund = min(amount, float(bill.amount_paid or 0))
        if refund > 0:
            bill.refund_amount = round(float(bill.refund_amount or 0) + refund, 2)
            bill.amount_paid = round(max(float(bill.amount_paid or 0) - refund, 0), 2)
            bill.payment_status = "refunded" if bill.amount_paid <= 0 else "partial"
            record_payment(db, bill, -refund, data.get("method") or bill.payment_method, user.id, kind="refund", note=document.document_no)
    db.commit()
    db.refresh(document)
    return document


def purchase_return(db: Session, user, data: dict) -> PurchaseReturn:
    from app.api.v1.clinic_admin import debit_stock

    clinic_id = clinic_id_of(user)
    line = db.get(PurchaseLine, int(data["purchase_line_id"]))
    purchase = db.get(PurchaseInvoice, line.purchase_id) if line else None
    if not line or not purchase or purchase.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="Purchase line not found")
    qty = float(data.get("quantity") or 0)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Enter the quantity to return")
    medicine = db.get(MedicineItem, line.medicine_id) if line.medicine_id else None
    pack = medicine.pack_size if medicine else 1
    strip = medicine.strip_size if medicine else 1
    base_qty = to_base_units(qty, line.unit or "tablet", pack or 1, strip or 1)
    remaining = float(line.base_quantity or 0) - float(line.returned_base or 0)
    if base_qty > remaining + 0.001:
        raise HTTPException(status_code=400, detail=f"Only {round(max(remaining, 0), 2)} base units remain on this line")
    reason = (data.get("reason") or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=400, detail="Enter a reason for the purchase return")
    portion = base_qty / float(line.base_quantity or base_qty or 1)
    amount = round(float(line.line_total or 0) * portion, 2)
    document = PurchaseReturn(
        clinic_id=clinic_id,
        purchase_id=purchase.id,
        supplier_id=purchase.supplier_id,
        document_no=_next_doc(db, clinic_id, PurchaseReturn, "document_no", "PR"),
        supplier_credit_no=(data.get("supplier_credit_no") or "").strip() or None,
        amount=amount,
        reason=reason,
        created_by=user.id,
    )
    db.add(document)
    db.flush()
    debit_stock(
        db, clinic_id, line.medicine_name, base_qty,
        batch_id=line.batch_id,
        txn_type="purchase_return",
        reason=reason,
        reference_type="purchase_return",
        reference_id=str(document.id),
        user_id=user.id,
    )
    line.returned_base = round(float(line.returned_base or 0) + base_qty, 2)
    db.add(PurchaseReturnLine(
        purchase_return_id=document.id,
        purchase_line_id=line.id,
        medicine_name=line.medicine_name,
        batch_no=line.batch_no,
        quantity=base_qty,
        amount=amount,
    ))
    db.commit()
    db.refresh(document)
    return document


def expiry_report(db: Session, clinic_id: int) -> dict:
    today = date.today()
    rows = db.query(StockBatch).filter(StockBatch.clinic_id == clinic_id, StockBatch.quantity > 0).all()
    buckets = {"expired": [], "within_30": [], "within_60": [], "within_90": []}
    near_value = 0.0
    for row in rows:
        if not row.expiry_date:
            continue
        item = {
            "id": row.id,
            "medicine_name": row.item_name,
            "batch_no": row.batch_no,
            "expiry_date": row.expiry_date.isoformat(),
            "quantity": row.quantity,
            "stock_status": row.stock_status or "saleable",
            "value": round(float(row.quantity or 0) * float(row.purchase_rate or row.selling_price or 0), 2),
        }
        days = (row.expiry_date - today).days
        if days < 0:
            buckets["expired"].append(item)
        elif days <= 30:
            buckets["within_30"].append(item)
            near_value += item["value"]
        elif days <= 60:
            buckets["within_60"].append(item)
        elif days <= 90:
            buckets["within_90"].append(item)
    return {"as_of": today.isoformat(), "near_expiry_value": round(near_value, 2), **buckets}


def stock_alerts(db: Session, clinic_id: int) -> dict:
    medicines = db.query(MedicineItem).filter_by(clinic_id=clinic_id, active=True).all()
    batches = db.query(StockBatch).filter(StockBatch.clinic_id == clinic_id, StockBatch.quantity > 0).all()
    on_hand: dict[str, float] = {}
    today = date.today()
    for batch in batches:
        if (batch.stock_status or "saleable") != "saleable":
            continue
        if batch.expiry_date and batch.expiry_date < today:
            continue
        key = batch.item_name.strip().lower()
        on_hand[key] = on_hand.get(key, 0) + float(batch.quantity or 0)
    low, out, reorder = [], [], []
    for medicine in medicines:
        qty = on_hand.get(medicine.brand_name.strip().lower(), 0)
        item = {"id": medicine.id, "brand_name": medicine.brand_name, "quantity": qty, "reorder_level": medicine.reorder_level or 0, "min_stock": medicine.min_stock or 0}
        if qty <= 0:
            out.append(item)
        elif medicine.min_stock and qty <= float(medicine.min_stock):
            low.append(item)
        if medicine.reorder_level and qty <= float(medicine.reorder_level):
            reorder.append(item)
    since = datetime.utcnow() - timedelta(days=90)
    movement = (
        db.query(InventoryTxn.medicine_name, InventoryTxn.quantity)
        .filter(InventoryTxn.clinic_id == clinic_id, InventoryTxn.created_at >= since, InventoryTxn.txn_type == "sale")
        .all()
    )
    sold: dict[str, float] = {}
    for name, qty in movement:
        sold[name] = sold.get(name, 0) + abs(float(qty or 0))
    fast = sorted(
        ({"medicine_name": name, "sold": round(qty, 2)} for name, qty in sold.items()),
        key=lambda row: row["sold"],
        reverse=True,
    )[:10]
    named = sorted({batch.item_name for batch in batches if sold.get(batch.item_name, 0) == 0})
    return {
        "low_stock": low,
        "out_of_stock": out,
        "reorder": reorder,
        "fast_moving": fast,
        "slow_moving": named[:20],
        "expired": expiry_report(db, clinic_id)["expired"],
    }


def availability(db: Session, clinic_id: int, names: list[str]) -> list[dict]:
    today = date.today()
    found = []
    for name in names:
        if not (name or "").strip():
            continue
        rows = (
            db.query(StockBatch)
            .filter(StockBatch.clinic_id == clinic_id, StockBatch.item_name.ilike(name.strip()), StockBatch.quantity > 0)
            .order_by(StockBatch.expiry_date.asc())
            .all()
        )
        saleable = [
            row for row in rows
            if (row.stock_status or "saleable") == "saleable" and (row.expiry_date is None or row.expiry_date >= today)
        ]
        found.append({
            "name": name,
            "saleable": round(sum(float(row.quantity or 0) for row in saleable), 2),
            "batches": [
                {
                    "id": row.id,
                    "batch_no": row.batch_no,
                    "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
                    "quantity": row.quantity,
                    "mrp": row.mrp,
                    "stock_status": row.stock_status or "saleable",
                }
                for row in rows
            ],
        })
    return found


def _method_bucket(method: str | None) -> str:
    text = (method or "").lower()
    if "cash" in text:
        return "cash"
    if "upi" in text:
        return "upi"
    if "card" in text:
        return "card"
    if "bank" in text or "transfer" in text:
        return "bank"
    return "other"


def _category_bucket(bill: Bill) -> str:
    category = (bill.category or bill.bill_type or "").lower()
    if category in {"pharmacy", "medicine"}:
        return "pharmacy"
    if category in {"lab", "investigation", "procedure"}:
        return "investigation"
    if category in {"visit", "consultation", "follow_up"}:
        return "consultation"
    return "other"


def report_period(preset: str, date_from: str | None, date_to: str | None):
    today = clinic_day(datetime.utcnow())
    if date_from and date_to:
        start = date.fromisoformat(date_from)
        end = date.fromisoformat(date_to)
    elif preset == "yesterday":
        start = end = today - timedelta(days=1)
    elif preset == "week":
        start, end = today - timedelta(days=6), today
    elif preset == "month":
        start, end = today.replace(day=1), today
    else:
        start = end = today
    if end < start:
        raise HTTPException(status_code=400, detail="The end date is before the start date")
    opening, closing = clinic_period_utc(start, end)
    return start, end, opening, closing


def finance_report(db: Session, user, preset: str, date_from: str | None, date_to: str | None) -> dict:
    start, end, opening, closing = report_period(preset, date_from, date_to)
    clinic_id = clinic_id_of(user)
    bills = (
        db.query(Bill)
        .join(Patient, Bill.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id,
            Bill.created_at >= opening,
            Bill.created_at < closing,
            Bill.payment_status != "cancelled",
        )
        .all()
    )
    payments = (
        db.query(BillPayment)
        .filter(BillPayment.clinic_id == clinic_id, BillPayment.created_at >= opening, BillPayment.created_at < closing)
        .all()
    )
    billed = consultation = pharmacy = investigation = other = discounts = 0.0
    patients = set()
    for bill in bills:
        billed += float(bill.amount or 0)
        discounts += float(bill.discount_amount or 0)
        patients.add(bill.patient_id)
        bucket = _category_bucket(bill)
        if bucket == "consultation":
            consultation += float(bill.amount or 0)
        elif bucket == "pharmacy":
            pharmacy += float(bill.amount or 0)
        elif bucket == "investigation":
            investigation += float(bill.amount or 0)
        else:
            other += float(bill.amount or 0)
    modes = {"cash": 0.0, "upi": 0.0, "card": 0.0, "bank": 0.0, "other": 0.0}
    collected = refunds = 0.0
    if payments:
        for payment in payments:
            modes[_method_bucket(payment.method)] += float(payment.amount or 0)
            if float(payment.amount or 0) < 0 or payment.kind == "refund":
                refunds += abs(float(payment.amount or 0))
            else:
                collected += float(payment.amount or 0)
    else:
        for bill in bills:
            paid = float(bill.amount_paid or 0)
            collected += paid
            modes[_method_bucket(bill.payment_method)] += paid
            refunds += float(bill.refund_amount or 0)
    outstanding = round(sum(max(float(bill.amount or 0) - float(bill.amount_paid or 0), 0) for bill in bills), 2)
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "billed": round(billed, 2),
        "consultation": round(consultation, 2),
        "pharmacy": round(pharmacy, 2),
        "investigation": round(investigation, 2),
        "other": round(other, 2),
        "collected": round(collected, 2),
        "outstanding": outstanding,
        "refunds": round(refunds, 2),
        "discounts": round(discounts, 2),
        "invoices": len(bills),
        "patients": len(patients),
        "average_per_patient": round(billed / len(patients), 2) if patients else 0,
        "payments": {key: round(value, 2) for key, value in modes.items()},
        "note": "B2C summary for this clinic. Hand the GST sheet to the accountant. It is not filed on the GST portal from here.",
    }


def patient_bills(db: Session, user, patient_id: int) -> list[dict]:
    from app.services.clinic_scope import ensure_patient_access

    patient = ensure_patient_access(db, patient_id, user)
    rows = db.query(Bill).filter_by(patient_id=patient.id).order_by(Bill.id.desc()).all()
    result = []
    for bill in rows:
        payments = db.query(BillPayment).filter_by(bill_id=bill.id).order_by(BillPayment.id.asc()).all()
        result.append({
            "id": bill.id,
            "invoice_number": bill.invoice_number,
            "created_at": bill.created_at.isoformat() if bill.created_at else None,
            "bill_type": bill.bill_type or bill.category,
            "description": bill.description,
            "amount": bill.amount,
            "gst_amount": bill.gst_amount or 0,
            "cgst_amount": bill.cgst_amount or 0,
            "sgst_amount": bill.sgst_amount or 0,
            "igst_amount": bill.igst_amount or 0,
            "amount_paid": bill.amount_paid or 0,
            "outstanding": round(max(float(bill.amount or 0) - float(bill.amount_paid or 0), 0), 2),
            "payment_status": bill.payment_status,
            "payment_method": bill.payment_method,
            "payments": [
                {"amount": payment.amount, "method": payment.method, "kind": payment.kind}
                for payment in payments
            ],
        })
    return result


def walk_in_sale(db: Session, user, data: dict):
    clinic_id = clinic_id_of(user)
    patient = db.query(Patient).filter(Patient.clinic_id == clinic_id, Patient.mrd_number == "WALKIN").first()
    if not patient:
        patient = Patient(
            clinic_id=clinic_id,
            mrd_number="WALKIN",
            name="Walk-in sale",
            age="—",
            sex="Other",
            doctor_id=owning_doctor_id(db, user),
        )
        db.add(patient)
        db.flush()
    visit = ensure_opd_visit_for_day(db, patient_id=patient.id, doctor_id=owning_doctor_id(db, user), visit_type="Pharmacy")
    db.commit()
    from app.api.v1.operations import create_bill
    from app.schemas.extended import BillCreate

    payload = dict(data)
    payload["visit_id"] = visit.id
    payload["category"] = "pharmacy"
    payload.pop("append_to_visit", None)
    return create_bill(BillCreate(**payload), user, db)


def alerts_xlsx(db: Session, clinic_id: int) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    report = stock_alerts(db, clinic_id)
    book = Workbook()
    sheet = book.active
    sheet.title = "Stock alerts"
    sheet.append(["Section", "Item", "Quantity", "Detail"])
    for row in report["low_stock"]:
        sheet.append(["Low", row["brand_name"], row["quantity"], row["reorder_level"]])
    for row in report["out_of_stock"]:
        sheet.append(["Out", row["brand_name"], row["quantity"], row["reorder_level"]])
    for row in report["expired"]:
        sheet.append(["Expired", row["medicine_name"], row["quantity"], row["expiry_date"]])
    for row in report["fast_moving"]:
        sheet.append(["Fast", row["medicine_name"], row["sold"], ""])
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def resolve_place_of_supply(db: Session, user, requested: str | None) -> str | None:
    profile = db.get(ClinicProfile, clinic_id_of(user))
    code = (requested or (profile.state_code if profile else "") or "").strip()
    if not code:
        return None
    if code not in STATE_CODES:
        raise HTTPException(status_code=400, detail="Choose a valid place of supply")
    return code


def record_advance(db: Session, user, patient_id: int, amount: float, method: str, note: str | None) -> PatientAdvance:
    from app.services.clinic_scope import ensure_patient_access

    patient = ensure_patient_access(db, patient_id, user)
    value = round(float(amount or 0), 2)
    if value <= 0:
        raise HTTPException(status_code=400, detail="Enter the advance amount")
    row = PatientAdvance(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        amount=value,
        balance=value,
        method=(method or "Cash").strip() or "Cash",
        note=(note or "").strip() or None,
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def advance_balance(db: Session, user, patient_id: int) -> dict:
    from app.services.clinic_scope import ensure_patient_access

    patient = ensure_patient_access(db, patient_id, user)
    rows = (
        db.query(PatientAdvance)
        .filter(PatientAdvance.patient_id == patient.id, PatientAdvance.balance > 0)
        .order_by(PatientAdvance.id.asc())
        .all()
    )
    return {
        "patient_id": patient.id,
        "balance": round(sum(float(row.balance or 0) for row in rows), 2),
    }


def apply_patient_advance(db: Session, clinic_id: int, patient_id: int, requested: float) -> float:
    left = round(float(requested or 0), 2)
    if left <= 0:
        return 0.0
    rows = (
        db.query(PatientAdvance)
        .filter(PatientAdvance.clinic_id == clinic_id, PatientAdvance.patient_id == patient_id, PatientAdvance.balance > 0)
        .order_by(PatientAdvance.id.asc())
        .all()
    )
    applied = 0.0
    for row in rows:
        take = round(min(float(row.balance or 0), left), 2)
        if take <= 0:
            continue
        row.balance = round(float(row.balance or 0) - take, 2)
        applied = round(applied + take, 2)
        left = round(left - take, 2)
        if left <= 0:
            break
    return applied


def issue_credit_note(db: Session, user, bill: Bill, amount: float, reason: str) -> TaxNote:
    value = round(float(amount or 0), 2)
    gross = float(bill.amount or 0) or value
    share = min(value / gross, 1) if gross else 1
    taxable = round(float(bill.base_amount or 0) * share, 2)
    gst = round(float(bill.gst_amount or 0) * share, 2)
    note = TaxNote(
        clinic_id=clinic_id_of_bill(db, bill),
        bill_id=bill.id,
        kind="credit",
        document_no=next_document_number(db, clinic_id_of_bill(db, bill), "CN"),
        taxable=taxable,
        gst_amount=gst,
        amount=value,
        reason=(reason or "").strip() or None,
        created_by=getattr(user, "id", None),
    )
    db.add(note)
    db.flush()
    bill.credit_note_number = note.document_no
    return note


def add_debit_note(db: Session, user, bill: Bill, taxable: float, gst_percent: float, reason: str) -> TaxNote:
    text = (reason or "").strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="Enter a reason for the debit note")
    base = round(float(taxable or 0), 2)
    if base <= 0:
        raise HTTPException(status_code=400, detail="Enter the debit amount")
    rate = float(gst_percent or 0)
    gst = round(base * rate / 100, 2)
    lines = _lines(bill)
    lines.append({
        "description": f"Debit — {text}"[:200],
        "procedure_code": bill.procedure_code,
        "quantity": 1,
        "rate": base,
        "base_amount": base,
        "gst_percent": rate,
        "gst_amount": gst,
    })
    base_sum = round(sum(float(line.get("base_amount") or 0) for line in lines), 2)
    gst_sum = round(sum(float(line.get("gst_amount") or 0) for line in lines), 2)
    discount = min(float(bill.discount_amount or 0), base_sum + gst_sum)
    payable, round_off = rupee_round(max(base_sum + gst_sum - discount, 0))
    bill.base_amount = base_sum
    bill.gst_amount = gst_sum
    bill.discount_amount = discount
    bill.amount = payable
    bill.round_off = round_off
    bill.line_items = json.dumps(lines)
    bill.description = ", ".join(line.get("description") or "" for line in lines)[:300]
    paid = float(bill.amount_paid or 0)
    bill.payment_status = "paid" if paid >= payable - 0.009 and payable > 0 else ("partial" if paid > 0 else "pending")
    apply_tax_split(db, user, bill)
    note = TaxNote(
        clinic_id=clinic_id_of_bill(db, bill),
        bill_id=bill.id,
        kind="debit",
        document_no=next_document_number(db, clinic_id_of_bill(db, bill), "DN"),
        taxable=base,
        gst_amount=gst,
        amount=round(base + gst, 2),
        reason=text,
        created_by=user.id,
    )
    db.add(note)
    db.flush()
    bill.debit_note_number = note.document_no
    return note


def gst_summary(db: Session, user, preset: str, date_from: str | None, date_to: str | None) -> dict:
    start, end, opening, closing = report_period(preset, date_from, date_to)
    clinic_id = clinic_id_of(user)
    bills = (
        db.query(Bill)
        .join(Patient, Bill.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id,
            Bill.created_at >= opening,
            Bill.created_at < closing,
            Bill.payment_status.notin_(["cancelled", "draft"]),
        )
        .all()
    )
    rates: dict[str, dict] = {}
    taxable = cgst = sgst = igst = 0.0
    for bill in bills:
        taxable += float(bill.base_amount or 0)
        cgst += float(bill.cgst_amount or 0)
        sgst += float(bill.sgst_amount or 0)
        igst += float(bill.igst_amount or 0)
        interstate = float(bill.igst_amount or 0) > 0 and float(bill.cgst_amount or 0) == 0
        for line in _lines(bill) or [{
            "base_amount": bill.base_amount or 0,
            "gst_percent": bill.gst_percent or 0,
            "gst_amount": bill.gst_amount or 0,
        }]:
            key = f"{float(line.get('gst_percent') or 0):g}"
            bucket = rates.setdefault(key, {"gst_percent": float(line.get("gst_percent") or 0), "taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0})
            line_tax = float(line.get("gst_amount") or 0)
            bucket["taxable"] = round(bucket["taxable"] + float(line.get("base_amount") or 0), 2)
            if interstate:
                bucket["igst"] = round(bucket["igst"] + line_tax, 2)
            else:
                half = round(line_tax / 2, 2)
                bucket["cgst"] = round(bucket["cgst"] + half, 2)
                bucket["sgst"] = round(bucket["sgst"] + (line_tax - half), 2)
    credits = (
        db.query(TaxNote)
        .filter(TaxNote.clinic_id == clinic_id, TaxNote.kind == "credit", TaxNote.created_at >= opening, TaxNote.created_at < closing)
        .all()
    )
    debits = (
        db.query(TaxNote)
        .filter(TaxNote.clinic_id == clinic_id, TaxNote.kind == "debit", TaxNote.created_at >= opening, TaxNote.created_at < closing)
        .all()
    )
    sale_credits = (
        db.query(SalesReturn)
        .filter(SalesReturn.clinic_id == clinic_id, SalesReturn.created_at >= opening, SalesReturn.created_at < closing)
        .all()
    )
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "rates": [rates[key] for key in sorted(rates, key=lambda item: float(item))],
        "invoice_totals": {
            "invoices": len(bills),
            "taxable": round(taxable, 2),
            "cgst": round(cgst, 2),
            "sgst": round(sgst, 2),
            "igst": round(igst, 2),
        },
        "credit_notes": {
            "count": len(credits) + len(sale_credits),
            "taxable": round(sum(float(row.taxable or 0) for row in credits), 2),
            "gst": round(sum(float(row.gst_amount or 0) for row in credits), 2),
            "amount": round(sum(float(row.amount or 0) for row in credits) + sum(float(row.amount or 0) for row in sale_credits), 2),
        },
        "debit_notes": {
            "count": len(debits),
            "taxable": round(sum(float(row.taxable or 0) for row in debits), 2),
            "gst": round(sum(float(row.gst_amount or 0) for row in debits), 2),
            "amount": round(sum(float(row.amount or 0) for row in debits), 2),
        },
    }


def gst_summary_csv(summary: dict) -> str:
    lines = ["Type,Rate,Taxable,CGST,SGST,IGST,Count"]
    for row in summary["rates"]:
        lines.append(
            f"Outward,{row['gst_percent']},{row['taxable']},{row['cgst']},{row['sgst']},{row['igst']},"
        )
    totals = summary["invoice_totals"]
    lines.append(f"Invoice total,,{totals['taxable']},{totals['cgst']},{totals['sgst']},{totals['igst']},{totals['invoices']}")
    credit = summary["credit_notes"]
    lines.append(f"Credit notes,,{credit['taxable']},,,,{credit['count']}")
    debit = summary["debit_notes"]
    lines.append(f"Debit notes,,{debit['taxable']},,,,{debit['count']}")
    return "\n".join(lines) + "\n"
