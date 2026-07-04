from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
import pandas as pd
import os
import json
from datetime import datetime
from models import db, User, Patient, Visit, GenericDrug, BrandMedication, Comorbidity, DiagnosisMaster, DrugComorbidityInteraction, Prescription
from forms import LoginForm, RegisterForm, PatientForm, VisitForm, PrescriptionForm, MedicationUploadForm, DiagnosisUploadForm
from pdf_service import (
    ensure_visit_pdf_columns,
    generate_prescription_pdf,
    get_visit_prescriptions,
    render_prescription_html,
    save_prescription_pdf_metadata,
    clamp_font_size,
    clamp_header_space,
    DEFAULT_FONT_SIZE,
    DEFAULT_HEADER_SPACE,
)
from medication_service import process_medication_rows, split_semaglutide_range_brands, sync_medication_template
from user_utils import ensure_user_columns, find_user_by_login, normalize_email
from prescription_utils import (
    ensure_prescription_columns,
    ensure_mg_unit,
    format_brand_label,
    format_prescription_dosage,
    format_prescription_drug_name,
    format_prescription_generic_name,
    get_or_create_manual_entry_brand,
    get_brand_prescription_counts,
    get_custom_prescription_counts,
    build_prescription_stats,
    is_insulin_brand,
    suggest_prescription_dosage,
)

app = Flask(__name__)
app.config.from_object('config.Config')

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_prescription_helpers():
    return {
        'format_brand_label': format_brand_label,
        'format_prescription_drug_name': format_prescription_drug_name,
        'format_prescription_generic_name': format_prescription_generic_name,
        'format_prescription_dosage': format_prescription_dosage,
    }

@app.route('/')
@login_required
def home():
    # Get recent visits
    recent_visits = Visit.query.join(Patient).filter(
        Visit.doctor_id == current_user.id
    ).order_by(Visit.visit_date.desc()).limit(10).all()
    
    total_patients = Patient.query.filter_by(doctor_id=current_user.id).count()
    total_visits = Visit.query.filter_by(doctor_id=current_user.id).count()
    total_drugs = GenericDrug.query.count()
    total_brands = BrandMedication.query.count()
    
    return render_template('index.html', 
                         visits=recent_visits,
                         total_patients=total_patients,
                         total_visits=total_visits,
                         total_drugs=total_drugs,
                         total_brands=total_brands)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = find_user_by_login(form.email.data)
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid email or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = normalize_email(form.email.data)
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(
            username=email,
            email=email,
            display_name=form.display_name.data.strip(),
            password=hashed_password,
            role='doctor',
            qualifications=form.qualifications.data,
            kmc_number=form.kmc_number.data,
        )
        try:
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('An account with this email already exists. Please login instead.', 'warning')
            return render_template('register.html', form=form)
        flash('Account created successfully! You can now login with your email.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from forms import ProfileForm
    form = ProfileForm()
    
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data.strip()
        current_user.qualifications = form.qualifications.data
        current_user.kmc_number = form.kmc_number.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    # Pre-populate form with existing data
    form.display_name.data = current_user.doctor_name
    form.qualifications.data = current_user.qualifications
    form.kmc_number.data = current_user.kmc_number
    
    return render_template('profile.html', form=form)

# Patient Management Routes
@app.route('/patients')
@login_required
def patients():
    # Search functionality
    search_query = request.args.get('search', '')
    search_type = request.args.get('search_type', 'name')
    
    query = Patient.query.filter_by(doctor_id=current_user.id)
    
    if search_query:
        if search_type == 'name':
            query = query.filter(Patient.name.ilike(f'%{search_query}%'))
        elif search_type == 'mrd':
            query = query.filter(Patient.mrd_number.ilike(f'%{search_query}%'))
        elif search_type == 'diagnosis':
            # Search in visits for diagnosis
            patient_ids = db.session.query(Visit.patient_id).filter(
                Visit.diagnosis.ilike(f'%{search_query}%')
            ).distinct().all()
            patient_ids = [pid[0] for pid in patient_ids]
            query = query.filter(Patient.id.in_(patient_ids))
    
    all_patients = query.order_by(Patient.date_registered.desc()).all()
    return render_template('patients.html', patients=all_patients, search_query=search_query, search_type=search_type)

@app.route('/patient/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    form = PatientForm()
    if form.validate_on_submit():
        patient = Patient(
            mrd_number=form.mrd_number.data,
            name=form.name.data,
            age=form.age.data,
            sex=form.sex.data,
            contact=form.contact.data,
            address=form.address.data,
            doctor_id=current_user.id
        )
        db.session.add(patient)
        db.session.commit()
        flash('Patient registered successfully!', 'success')
        return redirect(url_for('add_visit', patient_id=patient.id))
    return render_template('patient_form.html', form=form, title='Register New Patient')

@app.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if patient.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))
    
    visits = Visit.query.filter_by(patient_id=patient_id).order_by(Visit.visit_date.desc()).all()
    
    return render_template('patient_detail.html', patient=patient, visits=visits)

@app.route('/patient/<int:patient_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if patient.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))
    
    form = PatientForm()
    if form.validate_on_submit():
        patient.mrd_number = form.mrd_number.data
        patient.name = form.name.data
        patient.age = form.age.data
        patient.sex = form.sex.data
        patient.contact = form.contact.data
        patient.address = form.address.data
        db.session.commit()
        flash('Patient updated successfully!', 'success')
        return redirect(url_for('patient_detail', patient_id=patient.id))
    
    form.mrd_number.data = patient.mrd_number
    form.name.data = patient.name
    form.age.data = patient.age
    form.sex.data = patient.sex
    form.contact.data = patient.contact
    form.address.data = patient.address
    
    return render_template('patient_form.html', form=form, title='Edit Patient Demographics')

# Visit Management Routes
@app.route('/patient/<int:patient_id>/visit/add', methods=['GET', 'POST'])
@login_required
def add_visit(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if patient.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))
    
    form = VisitForm()
    
    # Get all diagnoses for the dropdown
    diagnoses = DiagnosisMaster.query.order_by(DiagnosisMaster.diagnosis_name).all()
    
    if form.validate_on_submit():
        # Calculate BMI if height and weight provided
        bmi = None
        if form.height.data and form.weight.data:
            height_m = form.height.data / 100
            bmi = round(form.weight.data / (height_m ** 2), 2)
        
        # Parse follow-up date
        follow_up_date = None
        if form.follow_up_date.data:
            try:
                follow_up_date = datetime.strptime(form.follow_up_date.data, '%Y-%m-%d').date()
            except:
                pass
        
        visit = Visit(
            patient_id=patient_id,
            visit_type=form.visit_type.data,
            chief_complaints=form.chief_complaints.data,
            height=form.height.data,
            weight=form.weight.data,
            bmi=bmi,
            bp_systolic=int(form.bp_systolic.data) if form.bp_systolic.data else None,
            bp_diastolic=int(form.bp_diastolic.data) if form.bp_diastolic.data else None,
            pulse=int(form.pulse.data) if form.pulse.data else None,
            temperature=form.temperature.data,
            spo2=int(form.spo2.data) if form.spo2.data else None,
            history=form.history.data,
            examination=form.examination.data,
            diagnosis=form.diagnosis_text.data,
            comorbidities=form.comorbidities.data,
            investigation=form.investigation.data,
            follow_up_date=follow_up_date,
            follow_up_notes=form.follow_up_notes.data,
            doctor_id=current_user.id
        )
        db.session.add(visit)
        db.session.commit()
        flash('Visit recorded successfully!', 'success')
        return redirect(url_for('visit_detail', visit_id=visit.id))
    
    # Show validation errors if any
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return render_template('visit_form.html', form=form, patient=patient, diagnoses=diagnoses, title='New Visit')

@app.route('/visit/<int:visit_id>')
@login_required
def visit_detail(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))
    
    prescriptions = Prescription.query.filter_by(visit_id=visit_id).all()
    warnings = []
    
    if visit.comorbidities:
        comorbidities_list = [c.strip() for c in visit.comorbidities.split(',')]
        for prescription in prescriptions:
            drug_warnings = check_drug_comorbidity_interactions(
                prescription.brand_medication.generic_drug_id,
                comorbidities_list
            )
            if drug_warnings:
                warnings.extend(drug_warnings)
    
    return render_template('visit_detail.html', visit=visit, prescriptions=prescriptions, warnings=warnings)

# Medication Management Routes
@app.route('/medications')
@login_required
def medications():
    generic_drugs = GenericDrug.query.order_by(GenericDrug.generic_name).all()
    brand_counts = get_brand_prescription_counts(current_user.id)
    custom_counts = get_custom_prescription_counts(current_user.id)
    prescription_stats = build_prescription_stats(generic_drugs, brand_counts, custom_counts)
    return render_template(
        'medications.html',
        drugs=generic_drugs,
        brand_counts=brand_counts,
        prescription_stats=prescription_stats,
    )

@app.route('/medications/upload', methods=['GET', 'POST'])
@login_required
def upload_medications():
    form = MedicationUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
            
            processed = process_medication_file(df)
            removed = processed.get('removed_count', 0)
            flash(
                f'Uploaded {processed["generic_count"]} new generics and {processed["brand_count"]} new brands.'
                + (f' Removed {removed} outdated entries.' if removed else ''),
                'success',
            )
            return redirect(url_for('medications'))
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
    
    return render_template('upload_medications.html', form=form)

# Diagnosis Management Routes
@app.route('/diagnoses')
@login_required
def diagnoses():
    all_diagnoses = DiagnosisMaster.query.order_by(DiagnosisMaster.category, DiagnosisMaster.diagnosis_name).all()
    return render_template('diagnoses.html', diagnoses=all_diagnoses)

@app.route('/diagnoses/upload', methods=['GET', 'POST'])
@login_required
def upload_diagnoses():
    form = DiagnosisUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
            
            processed = process_diagnosis_file(df)
            flash(f'Successfully uploaded {processed} diagnoses!', 'success')
            return redirect(url_for('diagnoses'))
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
    
    return render_template('upload_diagnoses.html', form=form)

# API Routes
@app.route('/api/search_generic', methods=['GET'])
@login_required
def search_generic():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    drugs = GenericDrug.query.filter(
        GenericDrug.generic_name.ilike(f'%{query}%')
    ).limit(10).all()
    
    results = [{
        'type': 'generic',
        'id': drug.id,
        'generic_name': drug.generic_name,
        'drug_class': drug.drug_class,
        'indication': drug.indication
    } for drug in drugs]

    brand_matches = BrandMedication.query.join(GenericDrug).filter(
        BrandMedication.brand_name.ilike(f'%{query}%')
    ).limit(10).all()

    seen_brand_ids = set()
    for brand in brand_matches:
        if brand.id in seen_brand_ids:
            continue
        seen_brand_ids.add(brand.id)
        results.append({
            'type': 'brand',
            'id': brand.generic_drug_id,
            'brand_id': brand.id,
            'generic_name': brand.generic_drug.generic_name,
            'brand_name': brand.brand_name,
            'display_label': format_brand_label(brand),
            'is_insulin': is_insulin_brand(brand),
            'strength': brand.strength,
            'formulation': brand.formulation,
            'suggested_dosage': suggest_prescription_dosage(brand),
            'drug_class': brand.generic_drug.drug_class,
        })
    
    return jsonify(results[:15])

@app.route('/api/get_brands/<int:generic_id>', methods=['GET'])
@login_required
def get_brands(generic_id):
    brands = BrandMedication.query.filter_by(generic_drug_id=generic_id).all()
    results = [{
        'id': brand.id,
        'brand_name': brand.brand_name,
        'display_label': format_brand_label(brand),
        'manufacturer': brand.manufacturer,
        'strength': brand.strength,
        'formulation': brand.formulation,
        'price': brand.price,
        'is_insulin': is_insulin_brand(brand),
        'suggested_dosage': suggest_prescription_dosage(brand),
    } for brand in brands]
    
    return jsonify(results)

# Prescription Routes
@app.route('/visit/<int:visit_id>/prescribe', methods=['GET', 'POST'])
@login_required
def add_prescription(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))
    
    return render_template('add_prescription.html', visit=visit)

@app.route('/api/add_prescription', methods=['POST'])
@login_required
def api_add_prescription():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    try:
        visit_id = int(data.get('visit_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid visit ID'}), 400

    custom_drug_name = (data.get('custom_drug_name') or '').strip()
    custom_generic_name = (data.get('custom_generic_name') or '').strip() or None
    dosage = (data.get('dosage') or '').strip() or None
    dose_morning = (data.get('dose_morning') or '').strip() or None
    dose_afternoon = (data.get('dose_afternoon') or '').strip() or None
    dose_evening = (data.get('dose_evening') or '').strip() or None
    frequency = (data.get('frequency') or '').strip() or None
    duration = (data.get('duration') or '').strip()
    timing = (data.get('timing') or '').strip() or None
    instructions = (data.get('instructions') or '').strip() or None

    has_insulin_doses = any([dose_morning, dose_afternoon, dose_evening])

    if not duration:
        return jsonify({'error': 'Duration is required'}), 400

    if custom_drug_name:
        brand = get_or_create_manual_entry_brand()
        brand_id = brand.id
    else:
        try:
            brand_id = int(data.get('brand_id'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Please select a brand or enter a custom drug name'}), 400
        brand = BrandMedication.query.get(brand_id)
        if not brand:
            return jsonify({'error': 'Brand not found'}), 404

    if dosage and brand and not custom_drug_name:
        formulation = (brand.formulation or '').strip().lower()
        if formulation in ('tablet', 'capsule'):
            dosage = ensure_mg_unit(dosage)

    if not has_insulin_doses and not dosage:
        return jsonify({'error': 'Enter dosage or insulin doses (morning/afternoon/evening)'}), 400
    if not has_insulin_doses and not frequency:
        return jsonify({'error': 'Frequency is required when insulin doses are not used'}), 400
    
    visit = Visit.query.get(visit_id)
    if not visit or visit.doctor_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    warnings = []
    if visit.comorbidities and not custom_drug_name:
        comorbidities_list = [c.strip() for c in visit.comorbidities.split(',') if c.strip()]
        warnings = check_drug_comorbidity_interactions(
            brand.generic_drug_id,
            comorbidities_list
        )
    
    warning_text = None
    if warnings:
        warning_text = '; '.join(
            w['recommendation'] for w in warnings if w.get('recommendation')
        ) or None

    prescription = Prescription(
        visit_id=visit_id,
        brand_medication_id=brand_id,
        custom_drug_name=custom_drug_name or None,
        custom_generic_name=custom_generic_name,
        dosage=dosage,
        dose_morning=dose_morning,
        dose_afternoon=dose_afternoon,
        dose_evening=dose_evening,
        frequency=frequency or ('Insulin dosing' if has_insulin_doses else None),
        timing=timing,
        duration=duration,
        instructions=instructions,
        warnings=warning_text
    )
    
    db.session.add(prescription)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'warnings': warnings,
        'prescription_id': prescription.id
    })

@app.route('/prescription/<int:prescription_id>/delete', methods=['POST'])
@login_required
def delete_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    visit = Visit.query.get(prescription.visit_id)
    
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))
    
    db.session.delete(prescription)
    db.session.commit()
    flash('Prescription deleted successfully!', 'success')
    return redirect(url_for('visit_detail', visit_id=visit.id))

def _resolve_font_size(visit):
    if request.args.get('font_size') is not None:
        return clamp_font_size(request.args.get('font_size'))
    if visit.pdf_font_size:
        return clamp_font_size(visit.pdf_font_size)
    return DEFAULT_FONT_SIZE

def _resolve_header_space(visit):
    if request.args.get('header_space') is not None:
        return clamp_header_space(request.args.get('header_space'))
    if visit.pdf_header_space is not None:
        return clamp_header_space(visit.pdf_header_space)
    return DEFAULT_HEADER_SPACE

def _build_visit_pdf(visit, doctor, font_size=None, header_space=None):
    font_size = clamp_font_size(font_size if font_size is not None else _resolve_font_size(visit))
    header_space = clamp_header_space(header_space if header_space is not None else _resolve_header_space(visit))
    pdf_result = generate_prescription_pdf(visit, doctor, font_size=font_size, header_space=header_space)
    save_prescription_pdf_metadata(
        visit, pdf_result['page_count'], font_size=font_size, header_space=header_space
    )
    return pdf_result

@app.route('/visit/<int:visit_id>/prescription/preview')
@login_required
def preview_prescription(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))

    font_size = _resolve_font_size(visit)
    header_space = _resolve_header_space(visit)
    prescriptions = get_visit_prescriptions(visit.id)
    html_preview = render_prescription_html(
        visit,
        visit.patient,
        prescriptions,
        current_user,
        preview=True,
        font_size=font_size,
        header_space=header_space,
    )

    return render_template(
        'prescription_preview.html',
        visit=visit,
        html_preview=html_preview,
        font_size=font_size,
        header_space=header_space,
    )

@app.route('/visit/<int:visit_id>/prescription/preview/html')
@login_required
def preview_prescription_html(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    font_size = _resolve_font_size(visit)
    header_space = _resolve_header_space(visit)
    prescriptions = get_visit_prescriptions(visit.id)
    return render_prescription_html(
        visit,
        visit.patient,
        prescriptions,
        current_user,
        preview=True,
        font_size=font_size,
        header_space=header_space,
    )

@app.route('/visit/<int:visit_id>/prescription/pdf')
@login_required
def preview_prescription_pdf(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))

    font_size = _resolve_font_size(visit)
    header_space = _resolve_header_space(visit)
    pdf_result = _build_visit_pdf(visit, current_user, font_size=font_size, header_space=header_space)

    return send_file(
        pdf_result['pdf_path'],
        mimetype='application/pdf',
        as_attachment=False,
        download_name=os.path.basename(pdf_result['pdf_path']),
    )

@app.route('/visit/<int:visit_id>/prescription/print')
@login_required
def print_prescription(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))

    font_size = _resolve_font_size(visit)
    header_space = _resolve_header_space(visit)
    _build_visit_pdf(visit, current_user, font_size=font_size, header_space=header_space)
    pdf_url = url_for(
        'preview_prescription_pdf',
        visit_id=visit.id,
        font_size=font_size,
        header_space=header_space,
    )

    return render_template(
        'print_prescription.html',
        visit=visit,
        pdf_url=pdf_url,
        font_size=font_size,
    )

@app.route('/generate_pdf/<int:visit_id>')
@login_required
def generate_pdf(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    if visit.doctor_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patients'))

    font_size = _resolve_font_size(visit)
    header_space = _resolve_header_space(visit)
    pdf_result = _build_visit_pdf(visit, current_user, font_size=font_size, header_space=header_space)
    flash(
        f'PDF generated at {font_size}pt ({pdf_result["page_count"]} page{"s" if pdf_result["page_count"] != 1 else ""}).',
        'success',
    )

    return send_file(
        pdf_result['pdf_path'],
        mimetype='application/pdf',
        as_attachment=True,
        download_name=os.path.basename(pdf_result['pdf_path']),
    )

# Helper Functions
def process_medication_file(df):
    required_columns = ['generic_name', 'brand_name']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f'Missing required column: {col}')

    return process_medication_rows(df.to_dict('records'))

def process_diagnosis_file(df):
    required_columns = ['diagnosis_name']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f'Missing required column: {col}')
    
    count = 0
    for _, row in df.iterrows():
        diagnosis_name = str(row['diagnosis_name']).strip()
        
        if not diagnosis_name:
            continue
        
        existing = DiagnosisMaster.query.filter_by(diagnosis_name=diagnosis_name).first()
        if not existing:
            diagnosis = DiagnosisMaster(
                diagnosis_name=diagnosis_name,
                category=row.get('category', ''),
                icd_code=row.get('icd_code', ''),
                description=row.get('description', '')
            )
            db.session.add(diagnosis)
            count += 1
    
    db.session.commit()
    return count

def check_drug_comorbidity_interactions(generic_drug_id, comorbidities_list):
    warnings = []
    
    for comorbidity_name in comorbidities_list:
        comorbidity = Comorbidity.query.filter(
            Comorbidity.name.ilike(f'%{comorbidity_name}%')
        ).first()
        
        if comorbidity:
            interactions = DrugComorbidityInteraction.query.filter_by(
                generic_drug_id=generic_drug_id,
                comorbidity_id=comorbidity.id
            ).all()
            
            for interaction in interactions:
                warnings.append({
                    'drug': interaction.generic_drug.generic_name,
                    'comorbidity': interaction.comorbidity.name,
                    'type': interaction.interaction_type,
                    'severity': interaction.severity,
                    'recommendation': interaction.recommendation
                })
    
    return warnings

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_visit_pdf_columns()
        ensure_prescription_columns()
        ensure_user_columns()
        split_semaglutide_range_brands()
        sync_medication_template()
    app.run(debug=True)
