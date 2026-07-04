# Quick Start Guide - Endocrinology EMR System

## Installation & Setup (5 minutes)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Populate Sample Data
```bash
python3 populate_sample_data.py
```

This creates:
- Demo doctor account
- 7 generic drugs (Metformin, Glimepiride, Sitagliptin, Empagliflozin, Insulin Glargine, Levothyroxine, Alendronate)
- 15 brand medications
- 7 comorbidities (CKD, Diabetic Nephropathy, Hypertension, Heart Failure, Liver Disease, Osteoporosis, CVD)
- 10 drug-comorbidity interaction rules
- 3 sample patients with prescriptions

### Step 3: Run the Application
```bash
python3 run.py
```

### Step 4: Login
Open browser to: http://localhost:5000/login

**Credentials:**
- Username: `demo_doctor`
- Password: `password123`

## Quick Feature Tour

### 1. Dashboard (Homepage)
- View statistics: patients, drugs, brands
- Quick access to recent patients
- Navigation sidebar

### 2. View Patients
Click "Patients" in sidebar
- See all patient records
- View comorbidities at a glance
- Quick actions: View, Edit, Prescribe

### 3. Add New Patient
Click "Add Patient"
- Enter patient details
- **Important**: Add comorbidities (comma-separated)
  - Example: `Chronic Kidney Disease, Hypertension`
- Save patient

### 4. Prescribe Medication (Key Feature!)
From patient detail page, click "Prescribe"

**Steps:**
1. **Search Generic Drug**: Type "met" → Select "Metformin"
2. **Select Brand**: Choose from dropdown (Glycomet, Glucophage, Obimet)
3. **Enter Details**:
   - Dosage: 500mg
   - Frequency: Twice daily
   - Duration: 30 days
   - Instructions: Take after meals
4. **Save**: System automatically checks drug-comorbidity interactions!

**Example Warning:**
If patient has "Chronic Kidney Disease" and you prescribe Metformin:
⚠️ **Warning**: Avoid in severe CKD (eGFR <30). Risk of lactic acidosis.

### 5. Upload Medications
Click "Upload Meds" in sidebar
1. Download sample template (button provided)
2. Fill in your medications
3. Upload CSV or Excel file
4. System automatically maps generic → brand relationships

### 6. View Medication Database
Click "Medications"
- Browse all generic drugs
- Expand to see brand options
- View pricing, strength, formulation

### 7. Generate Prescription PDF
From patient detail page:
- Click "Generate PDF"
- Professional prescription with all medications
- Includes warnings if present

## Sample Workflow: Complete Patient Visit

### Scenario: New diabetic patient with kidney disease

1. **Add Patient**
   - Name: John Doe
   - Age: 58
   - Comorbidities: `Chronic Kidney Disease, Hypertension`
   - Diagnosis: Type 2 Diabetes with CKD Stage 3

2. **Prescribe Medication**
   - Try prescribing Metformin
   - System shows: ⚠️ High severity warning about CKD
   - Choose alternative: Prescribe Sitagliptin instead
   - System shows: Dose adjustment required (50mg for moderate CKD)

3. **View Warnings**
   - Patient detail page shows all active warnings
   - Color-coded by severity (red=high, yellow=medium)

4. **Generate PDF**
   - Professional prescription ready for printing
   - Includes all warnings

## Key Drug-Comorbidity Interactions

### Pre-loaded in Sample Data:

1. **Metformin + CKD**
   - Type: Contraindicated
   - Severity: High
   - Recommendation: Avoid in severe CKD (eGFR <30)

2. **Empagliflozin + Heart Failure**
   - Type: Beneficial
   - Severity: Low
   - Recommendation: Recommended in HFrEF

3. **Glimepiride + Liver Disease**
   - Type: Caution
   - Severity: High
   - Recommendation: May cause hypoglycemia

4. **Alendronate + CKD**
   - Type: Contraindicated
   - Severity: High
   - Recommendation: Not for CrCl <35 ml/min

5. **Sitagliptin + CKD**
   - Type: Dose Adjustment
   - Severity: Medium
   - Recommendation: 50mg for moderate, 25mg for severe CKD

## Customization

### Add Your Own Medications
Two methods:

**Method 1: Upload CSV**
```csv
generic_name,brand_name,drug_class,manufacturer,strength,formulation,price
Dapagliflozin,Forxiga,SGLT2 Inhibitor,AstraZeneca,10mg,Tablet,120.00
```

**Method 2: Direct Database Entry**
Extend `populate_sample_data.py` with your drugs

### Add Drug-Comorbidity Rules
In `populate_sample_data.py`, add to `drugs_data`:
```python
'interactions': [
    {
        'comorbidity': 'Your Comorbidity',
        'type': 'contraindicated',  # or 'caution', 'dose-adjustment', 'beneficial'
        'severity': 'high',         # or 'medium', 'low'
        'recommendation': 'Your clinical recommendation here'
    }
]
```

## Tips for Best Use

1. **Always Enter Comorbidities**: The system can only help if comorbidities are recorded
2. **Use Generic Names First**: Search by generic, then choose brand
3. **Review Warnings**: Pay attention to severity levels
4. **Keep Database Updated**: Regularly upload new medications
5. **Use PDF Feature**: Professional prescriptions for patient records

## Troubleshooting

### Port Already in Use
```bash
# Kill existing Flask process
pkill -f "python.*run.py"
# Or use different port
python3 run.py  # Edit run.py to change port
```

### Database Issues
```bash
# Reset database
rm instance/emr.db
python3 populate_sample_data.py
```

### Missing Dependencies
```bash
pip install -r requirements.txt --upgrade
```

## Next Steps

1. ✅ Test with sample data
2. ✅ Upload your own medication list
3. ✅ Add drug-comorbidity rules for your practice
4. ✅ Customize for your specialty needs
5. ✅ Add more patients and prescriptions

## Support

- Check README.md for detailed documentation
- Review code comments for technical details
- Modify templates for UI customization

---

**Remember**: This is a demonstration system. For production use, ensure compliance with healthcare regulations and implement additional security measures.
