import os
import re
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.models import Prescription
from app.services.clinic_time import format_clinic_stamp
from app.services.specialty_templates import build_prescription_investigations
from app.services.prescription_utils import (
    format_prescription_dosage,
    format_prescription_drug_name,
    format_prescription_generic_name,
)

PDF_DIR = "static/prescriptions"
MIN_FONT_SIZE = 9
MAX_FONT_SIZE = 16
DEFAULT_FONT_SIZE = 12
MIN_HEADER_SPACE = 0
MAX_HEADER_SPACE = 100
DEFAULT_HEADER_SPACE = 0
MIN_LEFT_MARGIN = 0
MAX_LEFT_MARGIN = 40
DEFAULT_LEFT_MARGIN = 12
LINE_HEIGHTS = (1.12, 1.08, 1.05)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def clamp_font_size(font_size):
    try:
        size = int(font_size)
    except (TypeError, ValueError):
        return DEFAULT_FONT_SIZE
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))


def clamp_header_space(header_space):
    try:
        space = int(header_space)
    except (TypeError, ValueError):
        return DEFAULT_HEADER_SPACE
    return max(MIN_HEADER_SPACE, min(MAX_HEADER_SPACE, space))


def clamp_left_margin(left_margin):
    try:
        margin = int(left_margin)
    except (TypeError, ValueError):
        return DEFAULT_LEFT_MARGIN
    return max(MIN_LEFT_MARGIN, min(MAX_LEFT_MARGIN, margin))


def get_visit_prescriptions(db, visit_id):
    return db.query(Prescription).filter_by(visit_id=visit_id).all()


_REVIEW_ON = re.compile(r"^review on\s+(.+)$", re.IGNORECASE)


def _same_follow_up_day(raw: str, follow_up_date: date | None) -> bool:
    if follow_up_date is None:
        return False
    cleaned = re.sub(r"\s+", " ", raw.replace(",", " ")).strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date() == follow_up_date
        except ValueError:
            continue
    return False


def display_follow_up_notes(notes: str | None, follow_up_date: date | None) -> str:
    """Drop a notes line that only repeats the printed next-visit date."""
    kept = []
    for line in (notes or "").splitlines():
        text = line.strip()
        if not text:
            continue
        match = _REVIEW_ON.match(text)
        if match and _same_follow_up_day(match.group(1), follow_up_date):
            continue
        kept.append(text)
    return "\n".join(kept)


def render_prescription_html(
    visit, patient, prescriptions, doctor, preview=False,
    font_size=DEFAULT_FONT_SIZE, line_height=LINE_HEIGHTS[0],
    header_space=DEFAULT_HEADER_SPACE, left_margin=DEFAULT_LEFT_MARGIN,
    hide_patient_info=False,
    hide_header=False,
):
    font_size = clamp_font_size(font_size)
    header_space = clamp_header_space(header_space)
    left_margin = clamp_left_margin(left_margin)
    template = _jinja_env.get_template("prescription.html")
    investigations_text = build_prescription_investigations(visit)
    clinic = {"name": "Endo Clinic", "address": "", "phone": "", "gstin": "", "signatory": "", "signature_data": ""}
    try:
        from app.api.v1.clinic_admin import letterhead
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            clinic = letterhead(db, getattr(doctor, "clinic_id", None) or 1)
        finally:
            db.close()
    except Exception:
        pass
    return template.render(
        visit=visit,
        patient=patient,
        prescriptions=prescriptions,
        doctor=doctor,
        preview=preview,
        font_size=font_size,
        line_height=line_height,
        header_space=header_space,
        left_margin=left_margin,
        hide_patient_info=hide_patient_info,
        hide_header=hide_header,
        investigations_text=investigations_text,
        follow_up_notes_text=display_follow_up_notes(getattr(visit, "follow_up_notes", None), getattr(visit, "follow_up_date", None)),
        visit_stamp=format_clinic_stamp(getattr(visit, "visit_date", None)),
        clinic=clinic,
        format_prescription_drug_name=format_prescription_drug_name,
        format_prescription_generic_name=format_prescription_generic_name,
        format_prescription_dosage=format_prescription_dosage,
    )


def render_prescription_document(
    visit, patient, prescriptions, doctor, preview=False,
    font_size=DEFAULT_FONT_SIZE, line_height=LINE_HEIGHTS[0],
    header_space=DEFAULT_HEADER_SPACE, left_margin=DEFAULT_LEFT_MARGIN,
    hide_patient_info=False,
    hide_header=False,
):
    html = render_prescription_html(
        visit, patient, prescriptions, doctor,
        preview=preview, font_size=font_size, line_height=line_height,
        header_space=header_space, left_margin=left_margin,
        hide_patient_info=hide_patient_info,
        hide_header=hide_header,
    )
    return HTML(string=html).render()


def generate_prescription_pdf(
    db, visit, doctor,
    font_size=DEFAULT_FONT_SIZE,
    header_space=DEFAULT_HEADER_SPACE,
    left_margin=DEFAULT_LEFT_MARGIN,
    hide_patient_info=False,
    hide_header=False,
):
    font_size = clamp_font_size(font_size)
    header_space = clamp_header_space(header_space)
    left_margin = clamp_left_margin(left_margin)
    prescriptions = get_visit_prescriptions(db, visit.id)
    patient = visit.patient

    best_doc = None
    best_page_count = None
    best_line_height = LINE_HEIGHTS[0]

    for line_height in LINE_HEIGHTS:
        doc = render_prescription_document(
            visit, patient, prescriptions, doctor,
            font_size=font_size, line_height=line_height,
            header_space=header_space, left_margin=left_margin,
            hide_patient_info=hide_patient_info,
            hide_header=hide_header,
        )
        page_count = len(doc.pages)
        if best_page_count is None or page_count < best_page_count:
            best_doc = doc
            best_page_count = page_count
            best_line_height = line_height
        if page_count <= 1:
            break

    pdf_bytes = best_doc.write_pdf()

    os.makedirs(PDF_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in (patient.name or "")) or f"patient_{patient.id}"
    pdf_filename = f"prescription_{safe_name}_{visit.id}.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_filename)

    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(pdf_bytes)

    return {
        "pdf_bytes": pdf_bytes,
        "pdf_path": pdf_path,
        "page_count": best_page_count,
        "font_size": font_size,
        "header_space": header_space,
        "left_margin": left_margin,
        "line_height": best_line_height,
    }


def save_prescription_pdf_metadata(
    db, visit, page_count,
    font_size=None, header_space=None, left_margin=None,
    hide_patient_info=None,
    hide_header=None,
):
    visit.pdf_page_count = page_count
    visit.pdf_generated_at = datetime.utcnow()
    if font_size is not None:
        visit.pdf_font_size = clamp_font_size(font_size)
    if header_space is not None:
        visit.pdf_header_space = clamp_header_space(header_space)
    if left_margin is not None:
        visit.pdf_left_margin = clamp_left_margin(left_margin)
    if hide_patient_info is not None:
        visit.pdf_hide_patient_info = hide_patient_info
    if hide_header is not None:
        visit.pdf_hide_header = hide_header
    db.commit()
