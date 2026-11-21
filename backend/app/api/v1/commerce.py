"""Suppliers, purchases, returns, expiry, and finance reports."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models import PurchaseInvoice, PurchaseReturn, SalesReturn, Supplier
from app.services.clinic_scope import clinic_id_of
from app.services.commerce import (
    advance_balance,
    alerts_xlsx,
    availability,
    confirm_purchase,
    expiry_report,
    finance_report,
    gst_summary,
    gst_summary_csv,
    medicine_dict,
    patient_bills,
    pay_purchase,
    purchase_dict,
    purchase_return,
    record_advance,
    sales_return,
    save_medicine,
    save_supplier,
    search_medicines,
    stock_alerts,
    walk_in_sale,
)

router = APIRouter(prefix="/commerce", tags=["commerce"])
desk = require_role("billing", "pharmacy")
pharmacy = require_role("pharmacy")


@router.get("/finance/gst")
def gst(
    preset: str = "month",
    date_from: str | None = None,
    date_to: str | None = None,
    export: str | None = None,
    user=Depends(desk),
    db: Session = Depends(get_db),
):
    summary = gst_summary(db, user, preset, date_from, date_to)
    if export == "csv":
        return Response(
            content=gst_summary_csv(summary),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=gst-summary.csv"},
        )
    return summary


@router.post("/advances", status_code=201)
def create_advance(payload: dict, user=Depends(desk), db: Session = Depends(get_db)):
    row = record_advance(
        db,
        user,
        int(payload.get("patient_id") or 0),
        float(payload.get("amount") or 0),
        payload.get("method") or "Cash",
        payload.get("note"),
    )
    return {"id": row.id, "patient_id": row.patient_id, "amount": row.amount, "balance": row.balance, "method": row.method}


@router.get("/patients/{patient_id}/advance")
def patient_advance(patient_id: int, user=Depends(desk), db: Session = Depends(get_db)):
    return advance_balance(db, user, patient_id)


@router.get("/finance")
def finance(
    preset: str = "today",
    date_from: str | None = None,
    date_to: str | None = None,
    user=Depends(desk),
    db: Session = Depends(get_db),
):
    return finance_report(db, user, preset, date_from, date_to)


@router.get("/patients/{patient_id}/bills")
def bills_for_patient(patient_id: int, user=Depends(desk), db: Session = Depends(get_db)):
    return patient_bills(db, user, patient_id)


@router.get("/suppliers")
def list_suppliers(user=Depends(pharmacy), db: Session = Depends(get_db)):
    rows = db.query(Supplier).filter_by(clinic_id=clinic_id_of(user), active=True).order_by(Supplier.name).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "gstin": row.gstin,
            "drug_licence": row.drug_licence,
            "phone": row.phone,
            "email": row.email,
            "address": row.address,
            "payment_terms": row.payment_terms,
        }
        for row in rows
    ]


@router.post("/suppliers", status_code=201)
def create_supplier(payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    row = save_supplier(db, clinic_id_of(user), payload)
    return {"id": row.id, "name": row.name}


@router.get("/medicines")
def list_medicines(q: str = "", user=Depends(pharmacy), db: Session = Depends(get_db)):
    return [medicine_dict(row) for row in search_medicines(db, clinic_id_of(user), q)]


@router.post("/medicines", status_code=201)
def create_medicine(payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    return medicine_dict(save_medicine(db, clinic_id_of(user), payload))


@router.post("/purchases", status_code=201)
def create_purchase(payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    return purchase_dict(db, confirm_purchase(db, user, payload))


@router.get("/purchases")
def list_purchases(user=Depends(pharmacy), db: Session = Depends(get_db)):
    rows = (
        db.query(PurchaseInvoice)
        .filter_by(clinic_id=clinic_id_of(user))
        .order_by(PurchaseInvoice.id.desc())
        .limit(40)
        .all()
    )
    return [purchase_dict(db, row) for row in rows]


@router.post("/purchases/{purchase_id}/payments", status_code=201)
def purchase_payment(purchase_id: int, payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    row = pay_purchase(db, user, purchase_id, float(payload.get("amount") or 0))
    return purchase_dict(db, row)


@router.post("/sales-returns", status_code=201)
def create_sales_return(payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    row = sales_return(db, user, payload)
    return {"id": row.id, "document_no": row.document_no, "amount": row.amount, "condition": row.condition}


@router.get("/sales-returns")
def list_sales_returns(user=Depends(pharmacy), db: Session = Depends(get_db)):
    rows = db.query(SalesReturn).filter_by(clinic_id=clinic_id_of(user)).order_by(SalesReturn.id.desc()).limit(40).all()
    return [
        {"id": row.id, "document_no": row.document_no, "bill_id": row.bill_id, "amount": row.amount, "reason": row.reason, "condition": row.condition}
        for row in rows
    ]


@router.post("/purchase-returns", status_code=201)
def create_purchase_return(payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    row = purchase_return(db, user, payload)
    return {"id": row.id, "document_no": row.document_no, "amount": row.amount, "supplier_credit_no": row.supplier_credit_no}


@router.get("/purchase-returns")
def list_purchase_returns(user=Depends(pharmacy), db: Session = Depends(get_db)):
    rows = db.query(PurchaseReturn).filter_by(clinic_id=clinic_id_of(user)).order_by(PurchaseReturn.id.desc()).limit(40).all()
    return [
        {"id": row.id, "document_no": row.document_no, "amount": row.amount, "reason": row.reason, "supplier_credit_no": row.supplier_credit_no}
        for row in rows
    ]


@router.get("/expiry")
def expiry(user=Depends(pharmacy), db: Session = Depends(get_db)):
    return expiry_report(db, clinic_id_of(user))


@router.get("/stock-alerts")
def alerts(user=Depends(pharmacy), db: Session = Depends(get_db)):
    return stock_alerts(db, clinic_id_of(user))


@router.get("/stock-alerts/export")
def alerts_excel(user=Depends(pharmacy), db: Session = Depends(get_db)):
    body = alerts_xlsx(db, clinic_id_of(user))
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stock-alerts.xlsx"},
    )


@router.get("/availability")
def stock_availability(name: list[str] = Query(default=[]), user=Depends(desk), db: Session = Depends(get_db)):
    return availability(db, clinic_id_of(user), name)


@router.post("/walk-in", status_code=201)
def walk_in(payload: dict, user=Depends(pharmacy), db: Session = Depends(get_db)):
    return walk_in_sale(db, user, payload)
