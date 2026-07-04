import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import BrandMedication, Patient, Prescription, User, Visit
from app.schemas.prescription import PrescriptionResponse
from app.schemas.visit import InteractionWarning, VisitCreate, VisitDetailResponse, VisitResponse, VisitUpdate
from app.services.visit_service import apply_visit_fields, can_finalize_visit, ensure_visit_editable, finalize_visit_error
from app.services.clinical_safety import check_drug_comorbidity_interactions
from app.services.appointment_service import create_appointment_from_follow_up
from app.services.specialty_templates import (
    build_prescription_investigations,
    parse_specialty_data,
    specialty_fields_for_display,
    sync_template_to_labs,
)
from app.services.pdf_service import (
    DEFAULT_FONT_SIZE,
    DEFAULT_HEADER_SPACE,
    DEFAULT_LEFT_MARGIN,
    clamp_font_size,
    clamp_header_space,
    clamp_left_margin,
    generate_prescription_pdf,
    render_prescription_html,
    save_prescription_pdf_metadata,
)
from app.services.prescription_utils import enrich_prescription_response

router = APIRouter(tags=["visits"])


def _visit_response(visit: Visit) -> VisitResponse:
    data = VisitResponse.model_validate(visit)
    if visit.patient:
        data.patient_name = visit.patient.name
        data.patient_mrd = visit.patient.mrd_number
    return data


def _build_visit_detail(visit: Visit, db: Session) -> VisitDetailResponse:
    prescriptions = (
        db.query(Prescription)
        .options(joinedload(Prescription.brand_medication).joinedload(BrandMedication.generic_drug))
        .filter_by(visit_id=visit.id)
        .all()
    )
    warnings = []
    if visit.comorbidities:
        comorbidities_list = [c.strip() for c in visit.comorbidities.split(",")]
        for rx in prescriptions:
            if rx.brand_medication and rx.brand_medication.generic_drug_id:
                drug_warnings = check_drug_comorbidity_interactions(
                    db, rx.brand_medication.generic_drug_id, comorbidities_list
                )
                warnings.extend(drug_warnings)

    rx_responses = []
    for rx in prescriptions:
        base = PrescriptionResponse.model_validate(rx)
        extra = enrich_prescription_response(rx)
        rx_responses.append(base.model_copy(update=extra))

    base = _visit_response(visit)
    specialty_fields = specialty_fields_for_display(
        visit.specialty_template,
        parse_specialty_data(visit.specialty_data),
    )
    prevent_data = None
    if visit.prevent_data:
        try:
            prevent_data = json.loads(visit.prevent_data)
        except json.JSONDecodeError:
            prevent_data = None
    return VisitDetailResponse(
        **base.model_dump(),
        prescriptions=rx_responses,
        warnings=[InteractionWarning(**w) for w in warnings],
        specialty_fields=specialty_fields,
        investigations_text=build_prescription_investigations(visit),
        prevent_data=prevent_data,
        can_finalize=can_finalize_visit(db, visit),
    )


@router.post("/patients/{patient_id}/visits", response_model=VisitResponse, status_code=201)
def create_visit(
    patient_id: int,
    data: VisitCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Patient not found")

    bmi = None
    if data.height and data.weight:
        height_m = data.height / 100
        bmi = round(data.weight / (height_m ** 2), 2)

    visit = Visit(
        patient_id=patient_id,
        doctor_id=user.id,
        visit_type=data.visit_type,
        chief_complaints=data.chief_complaints,
        height=data.height,
        weight=data.weight,
        bmi=bmi,
        mid_parental_height=data.mid_parental_height,
        bp_systolic=data.bp_systolic,
        bp_diastolic=data.bp_diastolic,
        pulse=data.pulse,
        temperature=data.temperature,
        spo2=data.spo2,
        history=data.history,
        examination=data.examination,
        diagnosis=data.diagnosis,
        investigation=data.investigation,
        comorbidities=data.comorbidities,
        follow_up_date=data.follow_up_date,
        follow_up_notes=data.follow_up_notes,
        specialty_template=data.specialty_template,
        specialty_data=json.dumps(data.specialty_data) if data.specialty_data else None,
        prevent_data=json.dumps(data.prevent_data) if data.prevent_data else None,
    )
    db.add(visit)
    db.flush()

    if data.specialty_data and data.specialty_template:
        sync_template_to_labs(db, patient_id, visit.id, data.specialty_template, data.specialty_data)

    create_appointment_from_follow_up(db, visit, user.id)

    db.commit()
    db.refresh(visit)
    visit.patient = patient
    return _visit_response(visit)


@router.patch("/visits/{visit_id}", response_model=VisitResponse)
def update_visit(
    visit_id: int,
    data: VisitUpdate,
    autosave: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = db.query(Visit).options(joinedload(Visit.patient)).filter_by(id=visit_id).first()
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    ensure_visit_editable(visit)
    apply_visit_fields(visit, data, autosave=autosave)
    if data.specialty_data and data.specialty_template and not autosave:
        sync_template_to_labs(db, visit.patient_id, visit.id, data.specialty_template, data.specialty_data)
    create_appointment_from_follow_up(db, visit, user.id)
    db.commit()
    db.refresh(visit)
    visit.patient = db.get(Patient, visit.patient_id)
    return _visit_response(visit)


@router.post("/visits/{visit_id}/finalize", response_model=VisitResponse)
def finalize_visit(
    visit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    visit = db.query(Visit).options(joinedload(Visit.patient)).filter_by(id=visit_id).first()
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    ensure_visit_editable(visit)
    if not can_finalize_visit(db, visit):
        raise HTTPException(status_code=400, detail=finalize_visit_error())
    visit.status = "locked"
    visit.finalized_at = datetime.utcnow()
    db.commit()
    db.refresh(visit)
    return _visit_response(visit)


@router.get("/visits/{visit_id}", response_model=VisitDetailResponse)
def get_visit(
    visit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.patient))
        .filter_by(id=visit_id)
        .first()
    )
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    return _build_visit_detail(visit, db)


@router.get("/visits/{visit_id}/prescription/preview", response_class=HTMLResponse)
def preview_prescription_html(
    visit_id: int,
    font_size: int | None = None,
    header_space: int | None = None,
    left_margin: int | None = None,
    hide_patient_info: bool | None = None,
    hide_header: bool | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = db.query(Visit).options(joinedload(Visit.patient)).filter_by(id=visit_id).first()
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    from app.services.pdf_service import get_visit_prescriptions

    prescriptions = get_visit_prescriptions(db, visit.id)
    fs = clamp_font_size(font_size if font_size is not None else (visit.pdf_font_size or DEFAULT_FONT_SIZE))
    hs = clamp_header_space(header_space if header_space is not None else (visit.pdf_header_space or DEFAULT_HEADER_SPACE))
    lm = clamp_left_margin(left_margin if left_margin is not None else (visit.pdf_left_margin or DEFAULT_LEFT_MARGIN))
    hide_pt = hide_patient_info if hide_patient_info is not None else bool(visit.pdf_hide_patient_info or False)
    hide_hd = hide_header if hide_header is not None else bool(visit.pdf_hide_header or False)
    return render_prescription_html(
        visit, visit.patient, prescriptions, user,
        preview=True, font_size=fs, header_space=hs, left_margin=lm,
        hide_patient_info=hide_pt,
        hide_header=hide_hd,
    )


@router.get("/visits/{visit_id}/prescription/pdf")
def download_prescription_pdf(
    visit_id: int,
    font_size: int | None = None,
    header_space: int | None = None,
    left_margin: int | None = None,
    hide_patient_info: bool | None = None,
    hide_header: bool | None = None,
    download: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = db.query(Visit).options(joinedload(Visit.patient)).filter_by(id=visit_id).first()
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    fs = clamp_font_size(font_size if font_size is not None else (visit.pdf_font_size or DEFAULT_FONT_SIZE))
    hs = clamp_header_space(header_space if header_space is not None else (visit.pdf_header_space or DEFAULT_HEADER_SPACE))
    lm = clamp_left_margin(left_margin if left_margin is not None else (visit.pdf_left_margin or DEFAULT_LEFT_MARGIN))
    hide_pt = hide_patient_info if hide_patient_info is not None else bool(visit.pdf_hide_patient_info or False)
    hide_hd = hide_header if hide_header is not None else bool(visit.pdf_hide_header or False)
    result = generate_prescription_pdf(
        db, visit, user, font_size=fs, header_space=hs, left_margin=lm,
        hide_patient_info=hide_pt,
        hide_header=hide_hd,
    )
    save_prescription_pdf_metadata(
        db, visit, result["page_count"], font_size=fs, header_space=hs, left_margin=lm,
        hide_patient_info=hide_pt,
        hide_header=hide_hd,
    )
    filename = f"prescription_{visit.patient.name}_{visit.id}{'_DRAFT' if visit.status != 'locked' else ''}.pdf".replace(" ", "_")
    return Response(
        content=result["pdf_bytes"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}"'},
    )
