# MAJOR UPDATE IN PROGRESS - Visit-Based EMR System

## ⚠️ Important: Architectural Change

This update changes the EMR from a single-record-per-patient system to a **visit-based system** where:

1. **Patients** are registered once with demographics (name, age, MRD, contact)
2. **Visits** record each patient encounter with full clinical data
3. **Prescriptions** link to visits, not patients

## ✅ Completed So Far:

### 1. Database Models
- ✅ Separated Patient (demographics) from Visit (clinical data)
- ✅ Added DiagnosisMaster model for diagnosis dropdown
- ✅ Added chief_complaints field
- ✅ Visits track: complaints, vitals, examination, diagnosis, prescriptions

### 2. Forms
- ✅ Simplified PatientForm (demographics only)
- ✅ New VisitForm (full clinical data entry)
- ✅ DiagnosisUploadForm
- ✅ Diagnosis dropdown in VisitForm

### 3. Backend (app.py)
- ✅ Patient registration route
- ✅ Visit management routes
- ✅ Search functionality (name/MRD/diagnosis)
- ✅ Diagnosis upload and management
- ✅ Updated prescription routes to use visits

### 4. Templates
- ✅ patient_form.html (simple demographics)
- ✅ visit_form.html (full clinical data with chief complaints)

## 🚧 Still Needed:

### Critical Templates:
1. visit_detail.html - View visit with prescriptions
2. Updated patient_detail.html - Show visit history
3. Updated add_prescription.html - Link to visits
4. Updated patients.html - Add search functionality
5. Updated index.html - Show recent visits
6. diagnoses.html - Manage diagnoses
7. upload_diagnoses.html - Upload diagnosis list

### Updates:
- populate_sample_data.py needs update for Visit model
- prescription.html (PDF) needs visit support

## 🎯 New Features When Complete:

1. **Follow-up Visit System** ✅
   - Multiple visits per patient
   - Visit history tracking
   - Visit type (New/Follow-up/Emergency)

2. **Search Functionality** ✅
   - Search by patient name
   - Search by MRD/UHID number
   - Search by diagnosis

3. **Diagnosis Dropdown** ✅
   - Upload diagnosis list (CSV/Excel)
   - Select from dropdown during visit
   - Standardized diagnosis entry

4. **Chief Complaints Box** ✅
   - Dedicated field separate from history
   - Required field for every visit
   - Prominent display in visit details

## 📋 Workflow After Completion:

### Register New Patient:
1. Click "Add Patient"
2. Enter demographics (MRD, Name, Age, Sex, Contact)
3. Click "Register Patient"
4. Automatically redirected to "New Visit" form

### Record Visit:
1. Select visit type (New/Follow-up/Emergency)
2. Enter **Chief Complaints** (required)
3. Record vitals (auto-BMI calculation)
4. Enter history and examination
5. **Select diagnosis from dropdown** or enter custom
6. Add comorbidities for drug checking
7. Order investigations
8. Set follow-up date
9. Save visit

### Follow-up Visit:
1. Go to patient detail page
2. Click "New Visit" button
3. System creates new visit record
4. All previous visits visible in history
5. Can compare vitals, diagnoses across visits

### Search Patients:
1. Use search bar on patients page
2. Choose search type: Name / MRD / Diagnosis
3. Results filtered in real-time

## ⚠️ Database Migration Required

**IMPORTANT:** The new structure requires database recreation because:
- Patient model changed (removed clinical fields)
- New Visit model added
- New DiagnosisMaster model added
- Prescription now links to Visit, not Patient

**Steps:**
1. Backup existing database if needed
2. Delete old database: `rm instance/emr.db`
3. Run new populate script (when ready)
4. Test thoroughly before production use

## 🔄 Next Steps:

1. Complete remaining templates
2. Update populate_sample_data.py
3. Test complete workflow
4. Deploy to Render

## Status: ~60% Complete

Core architecture done, critical templates remaining.
