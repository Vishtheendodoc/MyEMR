"""Commercial billing, pharmacy stock, and returns

Revision ID: 008
Revises: 007
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _add(table: str, column: str, col: sa.Column) -> None:
    names = _names()
    if table not in names:
        return
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    if column not in existing:
        op.add_column(table, col)


def upgrade() -> None:
    names = _names()
    if "supplier" not in names:
        op.create_table(
            "supplier",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("gstin", sa.String(20)),
            sa.Column("drug_licence", sa.String(80)),
            sa.Column("phone", sa.String(30)),
            sa.Column("email", sa.String(150)),
            sa.Column("address", sa.Text()),
            sa.Column("payment_terms", sa.String(100)),
            sa.Column("active", sa.Boolean()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "medicine_item" not in names:
        op.create_table(
            "medicine_item",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("brand_name", sa.String(200), nullable=False),
            sa.Column("generic_name", sa.String(200)),
            sa.Column("composition", sa.String(300)),
            sa.Column("strength", sa.String(80)),
            sa.Column("dosage_form", sa.String(40)),
            sa.Column("manufacturer", sa.String(200)),
            sa.Column("category", sa.String(80)),
            sa.Column("schedule", sa.String(20)),
            sa.Column("hsn_code", sa.String(20)),
            sa.Column("gst_percent", sa.Float(), server_default="0"),
            sa.Column("purchase_price", sa.Float()),
            sa.Column("mrp", sa.Float()),
            sa.Column("selling_price", sa.Float()),
            sa.Column("barcode", sa.String(64)),
            sa.Column("min_stock", sa.Float(), server_default="0"),
            sa.Column("reorder_level", sa.Float(), server_default="10"),
            sa.Column("base_unit", sa.String(20)),
            sa.Column("pack_size", sa.Float(), server_default="1"),
            sa.Column("strip_size", sa.Float(), server_default="1"),
            sa.Column("active", sa.Boolean()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "inventory_txn" not in names:
        op.create_table(
            "inventory_txn",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("txn_type", sa.String(40), nullable=False),
            sa.Column("medicine_name", sa.String(200), nullable=False),
            sa.Column("batch_id", sa.Integer()),
            sa.Column("batch_no", sa.String(50)),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("previous_qty", sa.Float()),
            sa.Column("new_qty", sa.Float()),
            sa.Column("reference_type", sa.String(40)),
            sa.Column("reference_id", sa.String(40)),
            sa.Column("reason", sa.Text()),
            sa.Column("user_id", sa.Integer()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "purchase_invoice" not in names:
        op.create_table(
            "purchase_invoice",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id"), nullable=False),
            sa.Column("document_no", sa.String(30), nullable=False),
            sa.Column("supplier_invoice_no", sa.String(60), nullable=False),
            sa.Column("invoice_date", sa.Date(), nullable=False),
            sa.Column("amount", sa.Float()),
            sa.Column("gst_amount", sa.Float()),
            sa.Column("paid_amount", sa.Float()),
            sa.Column("status", sa.String(20)),
            sa.Column("created_by", sa.Integer()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "purchase_line" not in names:
        op.create_table(
            "purchase_line",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchase_invoice.id"), nullable=False),
            sa.Column("medicine_id", sa.Integer()),
            sa.Column("medicine_name", sa.String(200), nullable=False),
            sa.Column("batch_no", sa.String(50)),
            sa.Column("expiry_date", sa.Date()),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(20)),
            sa.Column("free_quantity", sa.Float()),
            sa.Column("base_quantity", sa.Float(), nullable=False),
            sa.Column("purchase_rate", sa.Float()),
            sa.Column("mrp", sa.Float()),
            sa.Column("selling_price", sa.Float()),
            sa.Column("gst_percent", sa.Float()),
            sa.Column("line_total", sa.Float()),
            sa.Column("batch_id", sa.Integer()),
            sa.Column("returned_base", sa.Float()),
        )
    if "bill_payment" not in names:
        op.create_table(
            "bill_payment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bill.id"), nullable=False),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("method", sa.String(40), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("note", sa.String(200)),
            sa.Column("user_id", sa.Integer()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "sales_return" not in names:
        op.create_table(
            "sales_return",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bill.id"), nullable=False),
            sa.Column("document_no", sa.String(30), nullable=False),
            sa.Column("amount", sa.Float()),
            sa.Column("reason", sa.String(300), nullable=False),
            sa.Column("condition", sa.String(20), nullable=False),
            sa.Column("created_by", sa.Integer()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "sales_return_line" not in names:
        op.create_table(
            "sales_return_line",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sales_return_id", sa.Integer(), sa.ForeignKey("sales_return.id"), nullable=False),
            sa.Column("description", sa.String(200), nullable=False),
            sa.Column("batch_no", sa.String(50)),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("amount", sa.Float()),
        )
    if "purchase_return" not in names:
        op.create_table(
            "purchase_return",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchase_invoice.id"), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id"), nullable=False),
            sa.Column("document_no", sa.String(30), nullable=False),
            sa.Column("supplier_credit_no", sa.String(60)),
            sa.Column("amount", sa.Float()),
            sa.Column("reason", sa.String(300), nullable=False),
            sa.Column("created_by", sa.Integer()),
            sa.Column("created_at", sa.DateTime()),
        )
    if "purchase_return_line" not in names:
        op.create_table(
            "purchase_return_line",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("purchase_return_id", sa.Integer(), sa.ForeignKey("purchase_return.id"), nullable=False),
            sa.Column("purchase_line_id", sa.Integer(), sa.ForeignKey("purchase_line.id"), nullable=False),
            sa.Column("medicine_name", sa.String(200), nullable=False),
            sa.Column("batch_no", sa.String(50)),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("amount", sa.Float()),
        )
    _add("bill", "bill_type", sa.Column("bill_type", sa.String(30)))
    _add("bill", "cgst_amount", sa.Column("cgst_amount", sa.Float(), server_default="0"))
    _add("bill", "sgst_amount", sa.Column("sgst_amount", sa.Float(), server_default="0"))
    _add("bill", "igst_amount", sa.Column("igst_amount", sa.Float(), server_default="0"))
    _add("stock_batch", "stock_status", sa.Column("stock_status", sa.String(20), server_default="saleable"))
    _add("stock_batch", "purchase_rate", sa.Column("purchase_rate", sa.Float()))
    _add("stock_batch", "mrp", sa.Column("mrp", sa.Float()))
    _add("stock_batch", "selling_price", sa.Column("selling_price", sa.Float()))
    _add("stock_batch", "gst_percent", sa.Column("gst_percent", sa.Float(), server_default="0"))
    _add("stock_batch", "medicine_id", sa.Column("medicine_id", sa.Integer()))
    _add("stock_batch", "supplier_id", sa.Column("supplier_id", sa.Integer()))
    _add("stock_batch", "mfg_date", sa.Column("mfg_date", sa.Date()))
    _add("stock_batch", "location", sa.Column("location", sa.String(80)))
    _add("prescription", "prescribed_quantity", sa.Column("prescribed_quantity", sa.Float()))
    _add("prescription", "dispensed_quantity", sa.Column("dispensed_quantity", sa.Float(), server_default="0"))
    _add("clinic_profile", "pharmacy_name", sa.Column("pharmacy_name", sa.String(150)))
    _add("clinic_profile", "drug_licence", sa.Column("drug_licence", sa.String(80)))
    _add("clinic_profile", "state_code", sa.Column("state_code", sa.String(10)))
    _add("clinic_profile", "tax_mode", sa.Column("tax_mode", sa.String(20), server_default="split"))
    _add("clinic_profile", "invoice_terms", sa.Column("invoice_terms", sa.Text()))
    _add("day_close", "opening_cash", sa.Column("opening_cash", sa.Float(), server_default="0"))
    _add("day_close", "closing_cash", sa.Column("closing_cash", sa.Float(), server_default="0"))


def downgrade() -> None:
    names = _names()
    for name in (
        "purchase_return_line",
        "purchase_return",
        "sales_return_line",
        "sales_return",
        "bill_payment",
        "purchase_line",
        "purchase_invoice",
        "inventory_txn",
        "medicine_item",
        "supplier",
    ):
        if name in names:
            op.drop_table(name)
