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
    with engine.begin() as conn:
      for s in stmts:
        conn.execute(text(s))
  if "patient" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("patient")}
    if "date_of_birth" not in cols:
      with engine.begin() as conn:
        conn.execute(text("ALTER TABLE patient ADD COLUMN date_of_birth DATE"))
