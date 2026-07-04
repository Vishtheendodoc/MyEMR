from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=True, index=True)
    display_name = db.Column(db.String(150), nullable=True)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="doctor")
    qualifications = db.Column(db.String(200))
    kmc_number = db.Column(db.String(50))

    @property
    def doctor_name(self):
        return (self.display_name or self.username or '').strip()

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mrd_number = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.String(10), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    contact = db.Column(db.String(50))
    address = db.Column(db.Text)
    
    date_registered = db.Column(db.DateTime, default=datetime.utcnow)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    visits = db.relationship('Visit', backref='patient', lazy=True, cascade='all, delete-orphan')

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    visit_date = db.Column(db.DateTime, default=datetime.utcnow)
    visit_type = db.Column(db.String(50), default='New Visit')
    
    # Chief Complaints
    chief_complaints = db.Column(db.Text)
    
    # Vitals
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    bmi = db.Column(db.Float)
    bp_systolic = db.Column(db.Integer)
    bp_diastolic = db.Column(db.Integer)
    pulse = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    spo2 = db.Column(db.Integer)
    
    # Clinical Information
    history = db.Column(db.Text)
    examination = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    investigation = db.Column(db.Text)
    comorbidities = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    follow_up_notes = db.Column(db.Text)

    pdf_page_count = db.Column(db.Integer)
    pdf_generated_at = db.Column(db.DateTime)
    pdf_font_size = db.Column(db.Integer, default=12)
    pdf_header_space = db.Column(db.Integer, default=0)
    
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    prescriptions = db.relationship('Prescription', backref='visit', lazy=True, cascade='all, delete-orphan')

class GenericDrug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    generic_name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    drug_class = db.Column(db.String(100))
    indication = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    brands = db.relationship('BrandMedication', backref='generic_drug', lazy=True, cascade='all, delete-orphan')

class BrandMedication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand_name = db.Column(db.String(200), nullable=False)
    generic_drug_id = db.Column(db.Integer, db.ForeignKey('generic_drug.id'), nullable=False)
    manufacturer = db.Column(db.String(200))
    strength = db.Column(db.String(100))
    formulation = db.Column(db.String(100))
    price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comorbidity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DiagnosisMaster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    diagnosis_name = db.Column(db.String(300), unique=True, nullable=False)
    category = db.Column(db.String(100))
    icd_code = db.Column(db.String(20))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DrugComorbidityInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    generic_drug_id = db.Column(db.Integer, db.ForeignKey('generic_drug.id'), nullable=False)
    comorbidity_id = db.Column(db.Integer, db.ForeignKey('comorbidity.id'), nullable=False)
    interaction_type = db.Column(db.String(50), nullable=False)
    recommendation = db.Column(db.Text)
    severity = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    generic_drug = db.relationship('GenericDrug', backref='interactions')
    comorbidity = db.relationship('Comorbidity', backref='drug_interactions')

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visit.id'), nullable=False)
    brand_medication_id = db.Column(db.Integer, db.ForeignKey('brand_medication.id'), nullable=False)
    custom_drug_name = db.Column(db.String(300))
    custom_generic_name = db.Column(db.String(200))
    dosage = db.Column(db.String(100))
    dose_morning = db.Column(db.String(50))
    dose_afternoon = db.Column(db.String(50))
    dose_evening = db.Column(db.String(50))
    frequency = db.Column(db.String(100))
    timing = db.Column(db.String(100))
    duration = db.Column(db.String(100))
    instructions = db.Column(db.Text)
    warnings = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    brand_medication = db.relationship('BrandMedication', backref='prescriptions')
