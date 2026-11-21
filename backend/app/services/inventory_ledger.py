"""Every stock change writes one ledger row. Callers still update the batch quantity."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import InventoryTxn, StockBatch


def write_ledger(
    db: Session,
    batch: StockBatch,
    previous_qty: float,
    txn_type: str,
    *,
    reason: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    user_id: int | None = None,
) -> None:
    if batch.id is None:
        db.flush()
    new_qty = round(float(batch.quantity or 0), 2)
    previous = round(float(previous_qty or 0), 2)
    delta = round(new_qty - previous, 2)
    if abs(delta) < 0.0001:
        return
    db.add(InventoryTxn(
        clinic_id=batch.clinic_id,
        txn_type=txn_type,
        medicine_name=batch.item_name,
        batch_id=batch.id,
        batch_no=batch.batch_no,
        quantity=delta,
        previous_qty=previous,
        new_qty=new_qty,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        user_id=user_id,
    ))
