from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, FloatField, SelectMultipleField
from wtforms.validators import DataRequired, Length, ValidationError, Email

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    display_name = StringField('Doctor Name', validators=[DataRequired(), Length(min=2, max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    qualifications = StringField('Qualifications (e.g., MBBS, MD)', validators=[Length(max=200)])
    kmc_number = StringField('KMC Registration Number', validators=[Length(max=50)])
    submit = SubmitField('Register')

    def validate_email(self, field):
        from user_utils import email_exists
        if email_exists(field.data):
            raise ValidationError('An account with this email already exists. Please login instead.')

class PatientForm(FlaskForm):
    mrd_number = StringField('MRD/UHID Number', validators=[Length(max=50)])
    name = StringField('Patient Name', validators=[DataRequired(), Length(max=150)])
    age = StringField('Age', validators=[DataRequired()])
    sex = SelectField('Sex', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    contact = StringField('Contact Number', validators=[Length(max=50)])
    address = TextAreaField('Address')
    submit = SubmitField('Register Patient')

class VisitForm(FlaskForm):
    visit_type = SelectField('Visit Type', choices=[
        ('New Visit', 'New Visit'),
        ('Follow-up', 'Follow-up'),
        ('Emergency', 'Emergency')
    ], validators=[DataRequired()])
    
    # Chief Complaints
    chief_complaints = TextAreaField('Chief Complaints', validators=[DataRequired()])
    
    # Vitals
    height = FloatField('Height (cm)')
    weight = FloatField('Weight (kg)')
    bp_systolic = StringField('BP Systolic (mmHg)')
    bp_diastolic = StringField('BP Diastolic (mmHg)')
    pulse = StringField('Pulse (bpm)')
    temperature = FloatField('Temperature (°F)')
    spo2 = StringField('SpO2 (%)')
    
    # Clinical
    history = TextAreaField('History')
    examination = TextAreaField('Examination Findings')
    diagnosis_text = TextAreaField('Diagnosis')
    comorbidities = TextAreaField('Comorbidities (for drug optimization)')
    investigation = TextAreaField('Investigations Ordered')
    follow_up_date = StringField('Follow-up Date (YYYY-MM-DD)')
    follow_up_notes = TextAreaField('Follow-up Notes')
    
    submit = SubmitField('Save Visit')

class PrescriptionForm(FlaskForm):
    generic_name = StringField('Generic Drug Name', validators=[DataRequired()])
    dosage = StringField('Dosage', validators=[DataRequired()])
    frequency = SelectField('Frequency', choices=[
        ('OD', 'OD (Once Daily)'),
        ('BD', 'BD (Twice Daily)'),
        ('TID', 'TID (Three Times Daily)'),
        ('QID', 'QID (Four Times Daily)'),
        ('SOS', 'SOS (As Needed)'),
        ('STAT', 'STAT (Immediately)'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly')
    ], validators=[DataRequired()])
    timing = SelectField('Timing', choices=[
        ('1-0-0', '1-0-0 (Morning)'),
        ('0-1-0', '0-1-0 (Afternoon)'),
        ('0-0-1', '0-0-1 (Night)'),
        ('1-1-0', '1-1-0 (Morning & Afternoon)'),
        ('1-0-1', '1-0-1 (Morning & Night)'),
        ('0-1-1', '0-1-1 (Afternoon & Night)'),
        ('1-1-1', '1-1-1 (Three Times)'),
        ('Before Food', 'Before Food'),
        ('After Food', 'After Food'),
        ('With Food', 'With Food'),
        ('Empty Stomach', 'Empty Stomach'),
        ('Bedtime', 'Bedtime')
    ])
    duration = StringField('Duration', validators=[DataRequired()])
    instructions = TextAreaField('Instructions')
    submit = SubmitField('Add Prescription')

class MedicationUploadForm(FlaskForm):
    file = FileField('Upload Medication List (CSV/Excel)', validators=[
        DataRequired(),
        FileAllowed(['csv', 'xlsx', 'xls'], 'Only CSV and Excel files allowed!')
    ])
    submit = SubmitField('Upload')

class GenericDrugForm(FlaskForm):
    generic_name = StringField('Generic Name', validators=[DataRequired(), Length(max=200)])
    drug_class = StringField('Drug Class', validators=[Length(max=100)])
    indication = TextAreaField('Indication')
    submit = SubmitField('Save Drug')

class BrandMedicationForm(FlaskForm):
    brand_name = StringField('Brand Name', validators=[DataRequired(), Length(max=200)])
    generic_drug_id = SelectField('Generic Drug', coerce=int, validators=[DataRequired()])
    manufacturer = StringField('Manufacturer', validators=[Length(max=200)])
    strength = StringField('Strength', validators=[Length(max=100)])
    formulation = StringField('Formulation', validators=[Length(max=100)])
    price = FloatField('Price')
    submit = SubmitField('Save Brand')

class DiagnosisUploadForm(FlaskForm):
    file = FileField('Upload Diagnosis List (CSV/Excel)', validators=[
        DataRequired(),
        FileAllowed(['csv', 'xlsx', 'xls'], 'Only CSV and Excel files allowed!')
    ])
    submit = SubmitField('Upload')

class ProfileForm(FlaskForm):
    display_name = StringField('Doctor Name', validators=[DataRequired(), Length(min=2, max=150)])
    qualifications = StringField('Qualifications', validators=[Length(max=200)])
    kmc_number = StringField('KMC Registration Number', validators=[Length(max=50)])
    submit = SubmitField('Update Profile')
