import os
from datetime import datetime

from flask import render_template
from weasyprint import HTML
from werkzeug.utils import secure_filename

from models import db, Prescription

PDF_DIR = 'static/prescriptions'
MIN_FONT_SIZE = 9
MAX_FONT_SIZE = 16
DEFAULT_FONT_SIZE = 12
MIN_HEADER_SPACE = 0
MAX_HEADER_SPACE = 50
DEFAULT_HEADER_SPACE = 0
LINE_HEIGHTS = (1.12, 1.08, 1.05)


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


def ensure_visit_pdf_columns():
    """Add PDF metadata columns to existing SQLite databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if 'visit' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('visit')}
    statements = []
    if 'pdf_page_count' not in columns:
        statements.append('ALTER TABLE visit ADD COLUMN pdf_page_count INTEGER')
    if 'pdf_generated_at' not in columns:
        statements.append('ALTER TABLE visit ADD COLUMN pdf_generated_at DATETIME')
    if 'pdf_font_size' not in columns:
        statements.append(f'ALTER TABLE visit ADD COLUMN pdf_font_size INTEGER DEFAULT {DEFAULT_FONT_SIZE}')
    if 'pdf_header_space' not in columns:
        statements.append(f'ALTER TABLE visit ADD COLUMN pdf_header_space INTEGER DEFAULT {DEFAULT_HEADER_SPACE}')

    if not statements:
        return

    with db.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def get_visit_prescriptions(visit_id):
    return Prescription.query.filter_by(visit_id=visit_id).all()


def render_prescription_html(
    visit, patient, prescriptions, doctor, preview=False,
    font_size=DEFAULT_FONT_SIZE, line_height=LINE_HEIGHTS[0],
    header_space=DEFAULT_HEADER_SPACE,
):
    font_size = clamp_font_size(font_size)
    header_space = clamp_header_space(header_space)
    return render_template(
        'prescription.html',
        visit=visit,
        patient=patient,
        prescriptions=prescriptions,
        doctor=doctor,
        preview=preview,
        font_size=font_size,
        line_height=line_height,
        header_space=header_space,
    )


def render_prescription_document(
    visit, patient, prescriptions, doctor, preview=False,
    font_size=DEFAULT_FONT_SIZE, line_height=LINE_HEIGHTS[0],
    header_space=DEFAULT_HEADER_SPACE,
):
    html = render_prescription_html(
        visit, patient, prescriptions, doctor,
        preview=preview, font_size=font_size, line_height=line_height,
        header_space=header_space,
    )
    return HTML(string=html).render()


def generate_prescription_pdf(visit, doctor, font_size=DEFAULT_FONT_SIZE, header_space=DEFAULT_HEADER_SPACE):
    """Generate PDF using the tightest line spacing that minimizes page count."""
    font_size = clamp_font_size(font_size)
    header_space = clamp_header_space(header_space)
    prescriptions = get_visit_prescriptions(visit.id)
    patient = visit.patient

    best_doc = None
    best_page_count = None
    best_line_height = LINE_HEIGHTS[0]

    for line_height in LINE_HEIGHTS:
        doc = render_prescription_document(
            visit, patient, prescriptions, doctor,
            font_size=font_size, line_height=line_height, header_space=header_space,
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
    safe_name = secure_filename(patient.name) or f'patient_{patient.id}'
    pdf_filename = f'prescription_{safe_name}_{visit.id}.pdf'
    pdf_path = os.path.join(PDF_DIR, pdf_filename)

    with open(pdf_path, 'wb') as pdf_file:
        pdf_file.write(pdf_bytes)

    return {
        'pdf_bytes': pdf_bytes,
        'pdf_path': pdf_path,
        'page_count': best_page_count,
        'font_size': font_size,
        'header_space': header_space,
        'line_height': best_line_height,
    }


def save_prescription_pdf_metadata(visit, page_count, font_size=None, header_space=None):
    visit.pdf_page_count = page_count
    visit.pdf_generated_at = datetime.utcnow()
    if font_size is not None:
        visit.pdf_font_size = clamp_font_size(font_size)
    if header_space is not None:
        visit.pdf_header_space = clamp_header_space(header_space)
    db.session.commit()
