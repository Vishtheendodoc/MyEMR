"""Lightweight schema upgrades for SQLite dev databases."""

from sqlalchemy import inspect, text

from app.core.database import engine


def ensure_phase2_columns():
  inspector = inspect(engine)
  if "visit" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("visit")}
    stmts = []
    if "specialty_template" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN specialty_template VARCHAR(50)")
    if "specialty_data" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN specialty_data TEXT")
    if "pdf_left_margin" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN pdf_left_margin INTEGER DEFAULT 12")
    if "status" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN status VARCHAR(20) DEFAULT 'draft'")
    if "draft_updated_at" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN draft_updated_at DATETIME")
    if "finalized_at" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN finalized_at DATETIME")
    if "mid_parental_height" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN mid_parental_height FLOAT")
    if "pdf_hide_patient_info" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN pdf_hide_patient_info BOOLEAN DEFAULT 0")
    if "pdf_hide_header" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN pdf_hide_header BOOLEAN DEFAULT 0")
    if "prevent_data" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN prevent_data TEXT")
    if "ordered_investigations" not in cols:
      stmts.append("ALTER TABLE visit ADD COLUMN ordered_investigations TEXT")
    with engine.begin() as conn:
      for s in stmts:
        conn.execute(text(s))
  if "patient" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("patient")}
    stmts = []
    if "date_of_birth" not in cols:
      stmts.append("ALTER TABLE patient ADD COLUMN date_of_birth DATE")
    if "clinic_id" not in cols:
      stmts.append("ALTER TABLE patient ADD COLUMN clinic_id INTEGER DEFAULT 1")
    if "allergies" not in cols:
      stmts.append("ALTER TABLE patient ADD COLUMN allergies TEXT")
    if "problem_list" not in cols:
      stmts.append("ALTER TABLE patient ADD COLUMN problem_list TEXT")
    if "registration_status" not in cols:
      stmts.append("ALTER TABLE patient ADD COLUMN registration_status VARCHAR(20) DEFAULT 'active'")
    with engine.begin() as conn:
      for s in stmts:
        conn.execute(text(s))
      if "clinic_id" not in cols:
        # Share existing patients across the clinic (was siloed by creating user).
        conn.execute(text("UPDATE patient SET clinic_id = 1 WHERE clinic_id IS NULL OR clinic_id = 0"))
      if "registration_status" not in cols:
        conn.execute(text("UPDATE patient SET registration_status = 'active' WHERE registration_status IS NULL"))
      conn.execute(text(
        "UPDATE patient SET mrd_number = NULL "
        "WHERE registration_status = 'cancelled' AND mrd_number IS NOT NULL"
      ))
  if "user" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("user")}
    stmts = []
    if "clinic_id" not in cols:
      stmts.append("ALTER TABLE user ADD COLUMN clinic_id INTEGER DEFAULT 1")
    if "is_active" not in cols:
      stmts.append("ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1")
    with engine.begin() as conn:
      for s in stmts:
        conn.execute(text(s))
      if "clinic_id" not in cols:
        conn.execute(text("UPDATE user SET clinic_id = 1 WHERE clinic_id IS NULL OR clinic_id = 0"))
      if "is_active" not in cols:
        conn.execute(text("UPDATE user SET is_active = 1 WHERE is_active IS NULL"))
  if "bill" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("bill")}
    stmts = []
    if "base_amount" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN base_amount FLOAT")
    if "gst_percent" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN gst_percent FLOAT DEFAULT 0")
    if "gst_amount" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN gst_amount FLOAT DEFAULT 0")
    if "invoice_number" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN invoice_number VARCHAR(30)")
    if "discount_amount" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN discount_amount FLOAT DEFAULT 0")
    if "amount_paid" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN amount_paid FLOAT DEFAULT 0")
    if "line_items" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN line_items TEXT")
    if "category" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN category VARCHAR(30)")
    if "refund_amount" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN refund_amount FLOAT DEFAULT 0")
    if "refund_reason" not in cols:
      stmts.append("ALTER TABLE bill ADD COLUMN refund_reason VARCHAR(300)")
    with engine.begin() as conn:
      for s in stmts:
        conn.execute(text(s))
  if "appointment" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("appointment")}
    stmts = []
    for name, ddl in (
      ("token_number", "INTEGER"),
      ("height", "FLOAT"),
      ("weight", "FLOAT"),
      ("bp_systolic", "INTEGER"),
      ("bp_diastolic", "INTEGER"),
      ("pulse", "INTEGER"),
      ("temperature", "FLOAT"),
      ("spo2", "INTEGER"),
    ):
      if name not in cols:
        stmts.append(f"ALTER TABLE appointment ADD COLUMN {name} {ddl}")
    with engine.begin() as conn:
      for s in stmts:
        conn.execute(text(s))
  if "day_close" not in inspector.get_table_names():
    with engine.begin() as conn:
      conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS day_close (
          id INTEGER PRIMARY KEY,
          clinic_id INTEGER NOT NULL DEFAULT 1,
          close_date DATE NOT NULL,
          cash_total FLOAT DEFAULT 0,
          upi_total FLOAT DEFAULT 0,
          card_total FLOAT DEFAULT 0,
          other_total FLOAT DEFAULT 0,
          billed_total FLOAT DEFAULT 0,
          collected_total FLOAT DEFAULT 0,
          closed_by INTEGER,
          closed_at DATETIME,
          notes TEXT
        )
        """
      ))
  ensure_commerce_columns()


def ensure_commerce_columns():
    """Add commercial billing columns on databases created before this upgrade."""
    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    alters: list[str] = []

    def missing(table: str, column: str, ddl: str):
        if table not in names:
            return
        cols = {c["name"] for c in inspector.get_columns(table)}
        if column not in cols:
            alters.append(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    missing("user", "acting_doctor_id", "INTEGER")
    missing("user", "acting_clinic_id", "INTEGER")
    missing("prescription", "prescribed_quantity", "FLOAT")
    missing("prescription", "dispensed_quantity", "FLOAT DEFAULT 0")
    missing("prescription", "dispense_status", "VARCHAR(20) DEFAULT 'pending'")
    missing("prescription", "dispense_note", "TEXT")
    missing("bill", "bill_type", "VARCHAR(30)")
    missing("bill", "cgst_amount", "FLOAT DEFAULT 0")
    missing("bill", "sgst_amount", "FLOAT DEFAULT 0")
    missing("bill", "igst_amount", "FLOAT DEFAULT 0")
    missing("bill", "place_of_supply", "VARCHAR(10)")
    missing("bill", "round_off", "FLOAT DEFAULT 0")
    missing("bill", "advance_applied", "FLOAT DEFAULT 0")
    missing("bill", "credit_note_number", "VARCHAR(30)")
    missing("bill", "debit_note_number", "VARCHAR(30)")
    missing("clinic_profile", "pharmacy_name", "VARCHAR(150)")
    missing("clinic_profile", "drug_licence", "VARCHAR(80)")
    missing("clinic_profile", "state_code", "VARCHAR(10)")
    missing("clinic_profile", "tax_mode", "VARCHAR(20) DEFAULT 'split'")
    missing("clinic_profile", "invoice_terms", "TEXT")
    missing("clinic_profile", "reminder_clinic_name", "VARCHAR(150)")
    missing("clinic_profile", "reminder_doctor_name", "VARCHAR(150)")
    missing("stock_batch", "medicine_id", "INTEGER")
    missing("stock_batch", "supplier_id", "INTEGER")
    missing("stock_batch", "mfg_date", "DATE")
    missing("stock_batch", "purchase_rate", "FLOAT")
    missing("stock_batch", "mrp", "FLOAT")
    missing("stock_batch", "selling_price", "FLOAT")
    missing("stock_batch", "gst_percent", "FLOAT DEFAULT 0")
    missing("stock_batch", "location", "VARCHAR(80)")
    missing("stock_batch", "stock_status", "VARCHAR(20) DEFAULT 'saleable'")
    missing("day_close", "opening_cash", "FLOAT DEFAULT 0")
    missing("day_close", "closing_cash", "FLOAT DEFAULT 0")
    missing("appointment", "channel", "VARCHAR(20) DEFAULT 'in_clinic'")
    missing("message_contact", "list_kind", "VARCHAR(20) DEFAULT 'saved'")
    if alters:
        with engine.begin() as conn:
            for statement in alters:
                conn.execute(text(statement))
