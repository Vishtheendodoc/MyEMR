"""Financial-year document numbers for one clinic.

April to March is the year. A number already issued is never used again.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models import Bill, Patient, PurchaseReturn, SalesReturn, TaxNote
from app.services.clinic_time import clinic_wall_now

STATE_CODES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}


def financial_year_label(moment=None) -> str:
    now = moment or clinic_wall_now()
    start = now.year if now.month >= 4 else now.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def rupee_round(total: float) -> tuple[float, float]:
    exact = Decimal(str(round(float(total or 0), 2)))
    payable = exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return float(payable), float((payable - exact).quantize(Decimal("0.01")))


def _max_seq(values) -> int:
    best = 0
    for value in values:
        if not value:
            continue
        try:
            best = max(best, int(str(value).rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return best


def next_document_number(db: Session, clinic_id: int, kind: str) -> str:
    label = financial_year_label()
    prefix = f"{kind}-{label}-"
    numbers: list[str] = []
    if kind == "INV":
        numbers = [
            row[0]
            for row in (
                db.query(Bill.invoice_number)
                .join(Patient, Bill.patient_id == Patient.id)
                .filter(Patient.clinic_id == clinic_id, Bill.invoice_number.like(f"{prefix}%"))
                .all()
            )
        ]
    elif kind == "CN":
        numbers = [
            row[0]
            for row in db.query(SalesReturn.document_no).filter(
                SalesReturn.clinic_id == clinic_id, SalesReturn.document_no.like(f"{prefix}%")
            ).all()
        ]
        numbers += [
            row[0]
            for row in db.query(TaxNote.document_no).filter(
                TaxNote.clinic_id == clinic_id, TaxNote.kind == "credit", TaxNote.document_no.like(f"{prefix}%")
            ).all()
        ]
    elif kind == "DN":
        numbers = [
            row[0]
            for row in db.query(TaxNote.document_no).filter(
                TaxNote.clinic_id == clinic_id, TaxNote.kind == "debit", TaxNote.document_no.like(f"{prefix}%")
            ).all()
        ]
    elif kind == "PR":
        numbers = [
            row[0]
            for row in db.query(PurchaseReturn.document_no).filter(
                PurchaseReturn.clinic_id == clinic_id, PurchaseReturn.document_no.like(f"{prefix}%")
            ).all()
        ]
    else:
        raise ValueError(f"Unknown document kind {kind}")
    return f"{prefix}{_max_seq(numbers) + 1:05d}"
