"""
Sample data population script for Endocrinology EMR with Visit-based system
"""

from app import app
from models import db, User, Patient, Visit, GenericDrug, BrandMedication, Comorbidity, DrugComorbidityInteraction, Prescription
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def populate_sample_data():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        
        # Check if data already exists
        if GenericDrug.query.first():
            print("Sample data already exists. Skipping...")
            return
        
        print("\n1. Creating sample user...")
        user = User(
            username='demo_doctor',
            password=generate_password_hash('password123'),
            role='doctor',
            qualifications='MBBS, MD (Endocrinology)',
            kmc_number='KMC-12345'
        )
        db.session.add(user)
        db.session.commit()
        print(f"✓ Created user: {user.username}")
        
        print("\n2. Creating comorbidities...")
        comorbidities_data = [
            {'name': 'Chronic Kidney Disease', 'description': 'Reduced kidney function', 'severity': 'high'},
            {'name': 'Diabetic Nephropathy', 'description': 'Kidney damage from diabetes', 'severity': 'high'},
            {'name': 'Hypertension', 'description': 'High blood pressure', 'severity': 'medium'},
            {'name': 'Heart Failure', 'description': 'Reduced cardiac output', 'severity': 'high'},
            {'name': 'Liver Disease', 'description': 'Impaired liver function', 'severity': 'high'},
            {'name': 'Osteoporosis', 'description': 'Reduced bone density', 'severity': 'medium'},
            {'name': 'Cardiovascular Disease', 'description': 'Heart and blood vessel disease', 'severity': 'high'},
        ]
        
        comorbidities = {}
        for data in comorbidities_data:
            comorbidity = Comorbidity(**data)
            db.session.add(comorbidity)
            db.session.flush()
            comorbidities[data['name']] = comorbidity
            print(f"✓ Created comorbidity: {data['name']}")
        
        db.session.commit()
        
        print("\n3. Creating generic drugs and brands...")
        
        # Diabetes medications
        drugs_data = [
            {
                'generic': {'generic_name': 'Metformin', 'drug_class': 'Biguanide', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Glycomet', 'manufacturer': 'USV Ltd', 'strength': '500mg', 'formulation': 'Tablet', 'price': 12.50},
                    {'brand_name': 'Glucophage', 'manufacturer': 'Abbott', 'strength': '500mg', 'formulation': 'Tablet', 'price': 15.00},
                    {'brand_name': 'Obimet', 'manufacturer': 'Micro Labs', 'strength': '500mg', 'formulation': 'Tablet', 'price': 10.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'contraindicated', 'severity': 'high', 
                     'recommendation': 'Avoid in severe CKD (eGFR <30). Risk of lactic acidosis. Consider dose reduction in moderate CKD.'},
                    {'comorbidity': 'Liver Disease', 'type': 'caution', 'severity': 'high', 
                     'recommendation': 'Use with caution. Monitor liver function. Risk of lactic acidosis in hepatic impairment.'},
                ]
            },
            {
                'generic': {'generic_name': 'Glimepiride', 'drug_class': 'Sulfonylurea', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Amaryl', 'manufacturer': 'Sanofi', 'strength': '1mg', 'formulation': 'Tablet', 'price': 25.00},
                    {'brand_name': 'Glimestar', 'manufacturer': 'Sun Pharma', 'strength': '1mg', 'formulation': 'Tablet', 'price': 20.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'caution', 'severity': 'medium', 
                     'recommendation': 'Increased risk of hypoglycemia in renal impairment. Start with lower dose and monitor closely.'},
                    {'comorbidity': 'Liver Disease', 'type': 'caution', 'severity': 'high', 
                     'recommendation': 'May cause hypoglycemia in hepatic impairment. Consider alternative therapy.'},
                ]
            },
            {
                'generic': {'generic_name': 'Sitagliptin', 'drug_class': 'DPP-4 Inhibitor', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Januvia', 'manufacturer': 'MSD', 'strength': '100mg', 'formulation': 'Tablet', 'price': 85.00},
                    {'brand_name': 'Zita', 'manufacturer': 'Sun Pharma', 'strength': '100mg', 'formulation': 'Tablet', 'price': 65.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'dose-adjustment', 'severity': 'medium', 
                     'recommendation': 'Dose reduction required: 50mg for moderate CKD, 25mg for severe CKD.'},
                ]
            },
            {
                'generic': {'generic_name': 'Empagliflozin', 'drug_class': 'SGLT2 Inhibitor', 'indication': 'Type 2 Diabetes, Heart Failure'},
                'brands': [
                    {'brand_name': 'Jardiance', 'manufacturer': 'Boehringer Ingelheim', 'strength': '10mg', 'formulation': 'Tablet', 'price': 95.00},
                    {'brand_name': 'Empa', 'manufacturer': 'Cipla', 'strength': '10mg', 'formulation': 'Tablet', 'price': 75.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'contraindicated', 'severity': 'high', 
                     'recommendation': 'Not recommended if eGFR <20. Limited efficacy in moderate CKD. Monitor renal function.'},
                    {'comorbidity': 'Heart Failure', 'type': 'beneficial', 'severity': 'low', 
                     'recommendation': 'Recommended in heart failure with reduced ejection fraction. Cardiovascular benefits demonstrated.'},
                ]
            },
            {
                'generic': {'generic_name': 'Insulin Glargine', 'drug_class': 'Long-acting Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Lantus', 'manufacturer': 'Sanofi', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 850.00},
                    {'brand_name': 'Basalog', 'manufacturer': 'Biocon', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 650.00},
                    {'brand_name': 'Xglar', 'manufacturer': 'Lupin Ltd', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 700.00},
                    {'brand_name': 'Basaglar', 'manufacturer': 'Biocon', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 720.00},
                    {'brand_name': 'Basalog One', 'manufacturer': 'Biocon', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 680.00},
                    {'brand_name': 'Basugine', 'manufacturer': 'Biocon', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 660.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Human Insulin 30/70', 'drug_class': 'Short & Intermediate Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Huminsulin 30/70', 'manufacturer': 'Eli Lilly', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 350.00},
                    {'brand_name': 'Xsulin 30/70', 'manufacturer': 'Glenmark', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 320.00},
                    {'brand_name': 'Lupisulin 30/70', 'manufacturer': 'Lupin Ltd', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 310.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Insulin Regular', 'drug_class': 'Short-acting Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Huminsulin R', 'manufacturer': 'Eli Lilly', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 280.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Insulin NPH', 'drug_class': 'Intermediate Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Huminsulin N', 'manufacturer': 'Eli Lilly', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 290.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Insulin Lispro', 'drug_class': 'Rapid-acting Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Humalog Mix 25', 'manufacturer': 'Eli Lilly', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 750.00},
                    {'brand_name': 'Humalog', 'manufacturer': 'Eli Lilly', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 680.00},
                    {'brand_name': 'Lyumjev', 'manufacturer': 'Eli Lilly', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 900.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Insulin Aspart', 'drug_class': 'Rapid-acting Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Fiasp', 'manufacturer': 'Novo Nordisk', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 850.00},
                    {'brand_name': 'Novorapid', 'manufacturer': 'Novo Nordisk', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 720.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Insulin Degludec', 'drug_class': 'Ultra Long-acting Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Tresiba', 'manufacturer': 'Novo Nordisk', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 950.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Insulin Degludec + Aspart', 'drug_class': 'Premixed Insulin', 'indication': 'Type 1 & Type 2 Diabetes'},
                'brands': [
                    {'brand_name': 'Ryzodeg', 'manufacturer': 'Novo Nordisk', 'strength': '100 IU/ml', 'formulation': 'Injection', 'price': 880.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Dapagliflozin + Sitagliptin + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Dapaturn SM', 'manufacturer': 'Lupin Ltd', 'strength': '10/100/1000', 'formulation': 'Tablet', 'price': 238.00},
                    {'brand_name': 'Udapa Trio 500', 'manufacturer': 'USV Ltd', 'strength': '10/100/500', 'formulation': 'Tablet', 'price': 210.00},
                    {'brand_name': 'Udapa Trio 1000', 'manufacturer': 'USV Ltd', 'strength': '10/100/1000', 'formulation': 'Tablet', 'price': 238.00},
                    {'brand_name': 'Oxramet S XR', 'manufacturer': 'MSN Labs', 'strength': '10/100/1000', 'formulation': 'Tablet', 'price': 220.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'contraindicated', 'severity': 'high',
                     'recommendation': 'Contains Metformin and Dapagliflozin. Avoid in severe CKD. Dose-adjust Sitagliptin based on eGFR.'},
                ]
            },
        ]
        
        # Thyroid medications
        drugs_data.extend([
            {
                'generic': {'generic_name': 'Levothyroxine', 'drug_class': 'Thyroid Hormone', 'indication': 'Hypothyroidism'},
                'brands': [
                    {'brand_name': 'Eltroxin', 'manufacturer': 'GSK', 'strength': '50mcg', 'formulation': 'Tablet', 'price': 35.00},
                    {'brand_name': 'Thyronorm', 'manufacturer': 'Abbott', 'strength': '50mcg', 'formulation': 'Tablet', 'price': 32.00},
                ],
                'interactions': [
                    {'comorbidity': 'Cardiovascular Disease', 'type': 'caution', 'severity': 'high', 
                     'recommendation': 'Start with low dose and titrate slowly. May precipitate angina or arrhythmias.'},
                    {'comorbidity': 'Osteoporosis', 'type': 'caution', 'severity': 'medium', 
                     'recommendation': 'Long-term high doses may reduce bone mineral density. Monitor bone health.'},
                ]
            },
        ])
        
        # Cardiovascular medications
        drugs_data.extend([
            {
                'generic': {'generic_name': 'Telmisartan + Cilnidipine', 'drug_class': 'Antihypertensive Combination', 'indication': 'Hypertension'},
                'brands': [
                    {'brand_name': 'Telista CL', 'manufacturer': 'Lupin Ltd', 'strength': '40/10 mg', 'formulation': 'Tablet', 'price': 201.45},
                    {'brand_name': 'Dilnip T 10', 'manufacturer': 'Lupin Ltd', 'strength': '10/40 mg', 'formulation': 'Tablet', 'price': 315.00},
                    {'brand_name': 'Telplus 40', 'manufacturer': 'Sun Pharma', 'strength': '10/40 mg', 'formulation': 'Tablet', 'price': 200.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'caution', 'severity': 'medium',
                     'recommendation': 'Monitor renal function and potassium. May require dose adjustment in renal impairment.'},
                ]
            },
        ])

        # Osteoporosis medications
        drugs_data.extend([
            {
                'generic': {'generic_name': 'Alendronate', 'drug_class': 'Bisphosphonate', 'indication': 'Osteoporosis'},
                'brands': [
                    {'brand_name': 'Fosamax', 'manufacturer': 'MSD', 'strength': '70mg', 'formulation': 'Tablet', 'price': 120.00},
                    {'brand_name': 'Alendrate', 'manufacturer': 'Cipla', 'strength': '70mg', 'formulation': 'Tablet', 'price': 95.00},
                ],
                'interactions': [
                    {'comorbidity': 'Chronic Kidney Disease', 'type': 'contraindicated', 'severity': 'high', 
                     'recommendation': 'Contraindicated if CrCl <35 ml/min. Risk of accumulation and bone mineralization defects.'},
                ]
            },
        ])

        # Extended formulary medications
        drugs_data.extend([
            {
                'generic': {'generic_name': 'Dapagliflozin + Glimepiride + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Udapa Gold 1', 'manufacturer': 'USV Ltd', 'strength': '10/1/500', 'formulation': 'Tablet', 'price': 250.00},
                    {'brand_name': 'Udapa Gold 2', 'manufacturer': 'USV Ltd', 'strength': '10/2/500', 'formulation': 'Tablet', 'price': 280.00},
                    {'brand_name': 'GemerDapa XR 1', 'manufacturer': 'Sun Pharma', 'strength': '10/1/1000', 'formulation': 'Tablet', 'price': 280.00},
                    {'brand_name': 'GemerDapa XR 2', 'manufacturer': 'Sun Pharma', 'strength': '10/2/1000', 'formulation': 'Tablet', 'price': 300.00},
                    {'brand_name': 'Oxramet G XR 10/1/1000', 'manufacturer': 'Sun Pharma', 'strength': '10/1/1000', 'formulation': 'Tablet', 'price': 105.00},
                    {'brand_name': 'Oxramet G XR 10/2/1000', 'manufacturer': 'Sun Pharma', 'strength': '10/2/1000', 'formulation': 'Tablet', 'price': 119.00},
                    {'brand_name': 'Oxramet G XR 10/1/500', 'manufacturer': 'Sun Pharma', 'strength': '10/1/500', 'formulation': 'Tablet', 'price': 101.50},
                    {'brand_name': 'Oxramet G XR 10/2/500', 'manufacturer': 'Sun Pharma', 'strength': '10/2/500', 'formulation': 'Tablet', 'price': 112.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Glimepiride + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Zoryl M1', 'manufacturer': 'Intas Pharma', 'strength': '1/500 mg', 'formulation': 'Tablet', 'price': 95.00},
                    {'brand_name': 'Zoryl M2', 'manufacturer': 'Intas Pharma', 'strength': '2/500 mg', 'formulation': 'Tablet', 'price': 120.00},
                    {'brand_name': 'Gemer 1', 'manufacturer': 'Sun Pharma', 'strength': '1/500 mg', 'formulation': 'Tablet', 'price': 55.00},
                    {'brand_name': 'Gemer 2', 'manufacturer': 'Sun Pharma', 'strength': '2/500 mg', 'formulation': 'Tablet', 'price': 65.00},
                    {'brand_name': 'Gluconorm G 1', 'manufacturer': 'Lupin Ltd', 'strength': '1/500 mg', 'formulation': 'Tablet', 'price': 90.00},
                    {'brand_name': 'Gluconorm G 2', 'manufacturer': 'Lupin Ltd', 'strength': '2/500 mg', 'formulation': 'Tablet', 'price': 110.00},
                    {'brand_name': 'Glycomet GP 1', 'manufacturer': 'USV Ltd', 'strength': '1/500 mg', 'formulation': 'Tablet', 'price': 59.00},
                    {'brand_name': 'Glycomet GP 2', 'manufacturer': 'USV Ltd', 'strength': '2/500 mg', 'formulation': 'Tablet', 'price': 75.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Rosuvastatin', 'drug_class': 'Statin', 'indication': 'Hyperlipidemia'},
                'brands': [
                    {'brand_name': 'Rosumac 10', 'manufacturer': 'Macleods', 'strength': '10mg', 'formulation': 'Tablet', 'price': 150.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Rosuvastatin + Fenofibrate', 'drug_class': 'Lipid-lowering Combination', 'indication': 'Hyperlipidemia'},
                'brands': [
                    {'brand_name': 'Novostat TG 10', 'manufacturer': 'Lupin Ltd', 'strength': '10/160 mg', 'formulation': 'Tablet', 'price': 200.00},
                    {'brand_name': 'Fenocor R 10', 'manufacturer': 'Intas Pharma', 'strength': '160/10 mg', 'formulation': 'Tablet', 'price': 200.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Montelukast + Desloratadine', 'drug_class': 'Antiallergic Combination', 'indication': 'Allergic Rhinitis'},
                'brands': [
                    {'brand_name': 'Mondeslor 10', 'manufacturer': 'Sun Pharma', 'strength': '10/5 mg', 'formulation': 'Tablet', 'price': 168.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Esomeprazole + Domperidone', 'drug_class': 'GI Combination', 'indication': 'GERD'},
                'brands': [
                    {'brand_name': 'Somprez D 40', 'manufacturer': 'Sun Pharma', 'strength': '40/30 mg', 'formulation': 'Capsule', 'price': 166.50},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Empagliflozin + Linagliptin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Linapride E', 'manufacturer': 'Torrent Pharma', 'strength': '10/5 mg', 'formulation': 'Tablet', 'price': 180.00},
                    {'brand_name': 'Liralin EP', 'manufacturer': 'Torrent Pharma', 'strength': '25/5 mg', 'formulation': 'Tablet', 'price': 200.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Dapagliflozin + Linagliptin + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Linapride DM', 'manufacturer': 'Torrent Pharma', 'strength': '10/5/1000', 'formulation': 'Tablet', 'price': 280.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Empagliflozin + Linagliptin + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Linacip EM', 'manufacturer': 'Torrent Pharma', 'strength': '25/5/1000', 'formulation': 'Tablet', 'price': 350.00},
                    {'brand_name': 'Istamet EMpa 25', 'manufacturer': 'MSD', 'strength': '25/100/1000', 'formulation': 'Tablet', 'price': 350.00},
                    {'brand_name': 'Linapride EM', 'manufacturer': 'Torrent Pharma', 'strength': '25/5/1000', 'formulation': 'Tablet', 'price': 350.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Empagliflozin', 'drug_class': 'SGLT2 Inhibitor', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Xenia 25', 'manufacturer': 'USV Ltd', 'strength': '25mg', 'formulation': 'Tablet', 'price': 163.90},
                    {'brand_name': 'Empaneo', 'manufacturer': 'Intas Pharma', 'strength': '25mg', 'formulation': 'Tablet', 'price': 200.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Empagliflozin + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Xenia M', 'manufacturer': 'USV Ltd', 'strength': '12.5/500 mg', 'formulation': 'Tablet', 'price': 140.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Semaglutide', 'drug_class': 'GLP-1 Agonist', 'indication': 'Type 2 Diabetes / Weight Management'},
                'brands': [
                    {'brand_name': 'Semaneo', 'manufacturer': 'Intas Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 800.00},
                    {'brand_name': 'Semaneo', 'manufacturer': 'Intas Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 900.00},
                    {'brand_name': 'Semaneo', 'manufacturer': 'Intas Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1000.00},
                    {'brand_name': 'Semaneo', 'manufacturer': 'Intas Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1100.00},
                    {'brand_name': 'Semaneo', 'manufacturer': 'Intas Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1199.00},
                    {'brand_name': 'Noveltreat', 'manufacturer': 'Sun Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 1000.00},
                    {'brand_name': 'Noveltreat', 'manufacturer': 'Sun Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1100.00},
                    {'brand_name': 'Noveltreat', 'manufacturer': 'Sun Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1200.00},
                    {'brand_name': 'Noveltreat', 'manufacturer': 'Sun Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1600.00},
                    {'brand_name': 'Noveltreat', 'manufacturer': 'Sun Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 2000.00},
                    {'brand_name': 'Sundae pen', 'manufacturer': 'Sun Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 1200.00},
                    {'brand_name': 'Sundae pen', 'manufacturer': 'Sun Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1300.00},
                    {'brand_name': 'Sundae pen', 'manufacturer': 'Sun Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1400.00},
                    {'brand_name': 'Sundae pen', 'manufacturer': 'Sun Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1600.00},
                    {'brand_name': 'Sundae pen', 'manufacturer': 'Sun Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1800.00},
                    {'brand_name': 'Sundae vial', 'manufacturer': 'Sun Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 1100.00},
                    {'brand_name': 'Sundae vial', 'manufacturer': 'Sun Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1200.00},
                    {'brand_name': 'Sundae vial', 'manufacturer': 'Sun Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1300.00},
                    {'brand_name': 'Sundae vial', 'manufacturer': 'Sun Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1500.00},
                    {'brand_name': 'Sundae vial', 'manufacturer': 'Sun Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1600.00},
                    {'brand_name': 'Obeda', 'manufacturer': 'Intas Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 1000.00},
                    {'brand_name': 'Obeda', 'manufacturer': 'Intas Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1100.00},
                    {'brand_name': 'Obeda', 'manufacturer': 'Intas Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1200.00},
                    {'brand_name': 'Obeda', 'manufacturer': 'Intas Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1400.00},
                    {'brand_name': 'Obeda', 'manufacturer': 'Intas Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1500.00},
                    {'brand_name': 'Semaglyn', 'manufacturer': 'Lupin Ltd', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 950.00},
                    {'brand_name': 'Semaglyn', 'manufacturer': 'Lupin Ltd', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1050.00},
                    {'brand_name': 'Semaglyn', 'manufacturer': 'Lupin Ltd', 'strength': '1mg', 'formulation': 'Injection', 'price': 1150.00},
                    {'brand_name': 'Semaglyn', 'manufacturer': 'Lupin Ltd', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1300.00},
                    {'brand_name': 'Semaglyn', 'manufacturer': 'Lupin Ltd', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1400.00},
                    {'brand_name': 'Sembolic', 'manufacturer': 'Torrent Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 900.00},
                    {'brand_name': 'Sembolic', 'manufacturer': 'Torrent Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1000.00},
                    {'brand_name': 'Sembolic', 'manufacturer': 'Torrent Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1100.00},
                    {'brand_name': 'Sembolic', 'manufacturer': 'Torrent Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1250.00},
                    {'brand_name': 'Sembolic', 'manufacturer': 'Torrent Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1350.00},
                    {'brand_name': 'Semanat vial', 'manufacturer': 'Sun Pharma', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 1050.00},
                    {'brand_name': 'Semanat vial', 'manufacturer': 'Sun Pharma', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 1150.00},
                    {'brand_name': 'Semanat vial', 'manufacturer': 'Sun Pharma', 'strength': '1mg', 'formulation': 'Injection', 'price': 1250.00},
                    {'brand_name': 'Semanat vial', 'manufacturer': 'Sun Pharma', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 1400.00},
                    {'brand_name': 'Semanat vial', 'manufacturer': 'Sun Pharma', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 1550.00},
                    {'brand_name': 'Sematrinity', 'manufacturer': 'Sun Pharma', 'strength': '2mg', 'formulation': 'Injection', 'price': 750.00},
                    {'brand_name': 'Sematrinity', 'manufacturer': 'Sun Pharma', 'strength': '4mg', 'formulation': 'Injection', 'price': 1300.00},
                    {'brand_name': 'Ozempic', 'manufacturer': 'Novo Nordisk', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 3200.00},
                    {'brand_name': 'Ozempic', 'manufacturer': 'Novo Nordisk', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 3500.00},
                    {'brand_name': 'Ozempic', 'manufacturer': 'Novo Nordisk', 'strength': '1mg', 'formulation': 'Injection', 'price': 4000.00},
                    {'brand_name': 'Ozempic', 'manufacturer': 'Novo Nordisk', 'strength': '2mg', 'formulation': 'Injection', 'price': 4500.00},
                    {'brand_name': 'Wegovy', 'manufacturer': 'Novo Nordisk', 'strength': '0.25mg', 'formulation': 'Injection', 'price': 3500.00},
                    {'brand_name': 'Wegovy', 'manufacturer': 'Novo Nordisk', 'strength': '0.5mg', 'formulation': 'Injection', 'price': 3800.00},
                    {'brand_name': 'Wegovy', 'manufacturer': 'Novo Nordisk', 'strength': '1mg', 'formulation': 'Injection', 'price': 4200.00},
                    {'brand_name': 'Wegovy', 'manufacturer': 'Novo Nordisk', 'strength': '1.7mg', 'formulation': 'Injection', 'price': 4800.00},
                    {'brand_name': 'Wegovy', 'manufacturer': 'Novo Nordisk', 'strength': '2.4mg', 'formulation': 'Injection', 'price': 5500.00},
],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Domperidone + Rabeprazole', 'drug_class': 'GI Combination', 'indication': 'GERD'},
                'brands': [
                    {'brand_name': 'Veloz D', 'manufacturer': 'Torrent Pharma', 'strength': '30/20 mg', 'formulation': 'Capsule', 'price': 150.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Pancreatin', 'drug_class': 'Digestive Enzyme', 'indication': 'Pancreatic Insufficiency'},
                'brands': [
                    {'brand_name': 'Enzar HS', 'manufacturer': 'Torrent Pharma', 'strength': '250mg', 'formulation': 'Capsule', 'price': 180.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Nutritional Supplement', 'drug_class': 'Nutritional Supplement', 'indication': 'Diabetes Nutrition'},
                'brands': [
                    {'brand_name': 'Prohance D', 'manufacturer': 'Sun Pharma', 'strength': '200g', 'formulation': 'Powder', 'price': 400.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Dapagliflozin + Sitagliptin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Dapefy S', 'manufacturer': 'Sun Pharma', 'strength': '10/100', 'formulation': 'Tablet', 'price': 220.00},
                    {'brand_name': 'Oxra S', 'manufacturer': 'Sun Pharma', 'strength': '10/100', 'formulation': 'Tablet', 'price': 270.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Dapagliflozin', 'drug_class': 'SGLT2 Inhibitor', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Dapefy', 'manufacturer': 'Sun Pharma', 'strength': '10mg', 'formulation': 'Tablet', 'price': 205.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Glimepiride + Metformin + Voglibose', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Gemer V 1', 'manufacturer': 'Sun Pharma', 'strength': '1/500/0.2 mg', 'formulation': 'Tablet', 'price': 130.00},
                    {'brand_name': 'Gemer V 2', 'manufacturer': 'Sun Pharma', 'strength': '2/500/0.2 mg', 'formulation': 'Tablet', 'price': 150.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Glimepiride + Metformin + Pioglitazone', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Gluconorm PG 1', 'manufacturer': 'Lupin Ltd', 'strength': '1/500/15 mg', 'formulation': 'Tablet', 'price': 94.00},
                    {'brand_name': 'Gluconorm PG 2', 'manufacturer': 'Lupin Ltd', 'strength': '2/500/15 mg', 'formulation': 'Tablet', 'price': 119.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Empagliflozin + Sitagliptin + Metformin', 'drug_class': 'Antidiabetic Combination', 'indication': 'Type 2 Diabetes Mellitus'},
                'brands': [
                    {'brand_name': 'Empaneo SM', 'manufacturer': 'Intas Pharma', 'strength': '25/100/1000', 'formulation': 'Tablet', 'price': 350.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Gabapentin + Lidocaine', 'drug_class': 'Neuropathic Pain Agent', 'indication': 'Neuropathic Pain'},
                'brands': [
                    {'brand_name': 'Sentidor Gel', 'manufacturer': 'Anthem Biopharma', 'strength': '6/5%', 'formulation': 'Gel', 'price': 350.00},
                    {'brand_name': 'Gabacure Gel', 'manufacturer': 'HBC Lifesciences', 'strength': '6/5%', 'formulation': 'Gel', 'price': 300.00},
                ],
                'interactions': []
            },
            {
                'generic': {'generic_name': 'Urea + Allantoin', 'drug_class': 'Topical Emollient', 'indication': 'Diabetic Foot Care'},
                'brands': [
                    {'brand_name': 'FootSave Plus', 'manufacturer': 'Anthem Biopharma', 'strength': '50g', 'formulation': 'Cream', 'price': 155.00},
                ],
                'interactions': []
            },
        ])
        
        for drug_data in drugs_data:
            # Create generic drug
            generic = GenericDrug(**drug_data['generic'])
            db.session.add(generic)
            db.session.flush()
            print(f"✓ Created generic drug: {generic.generic_name}")
            
            # Create brands
            for brand_data in drug_data['brands']:
                brand = BrandMedication(generic_drug_id=generic.id, **brand_data)
                db.session.add(brand)
                print(f"  - Brand: {brand_data['brand_name']}")
            
            # Create interactions
            for interaction_data in drug_data['interactions']:
                comorbidity_name = interaction_data.pop('comorbidity')
                if comorbidity_name in comorbidities:
                    interaction = DrugComorbidityInteraction(
                        generic_drug_id=generic.id,
                        comorbidity_id=comorbidities[comorbidity_name].id,
                        interaction_type=interaction_data['type'],
                        severity=interaction_data['severity'],
                        recommendation=interaction_data['recommendation']
                    )
                    db.session.add(interaction)
                    print(f"  - Interaction: {comorbidity_name} ({interaction_data['type']})")
        
        db.session.commit()
        
        print("\n4. Creating sample patients...")
        patients_data = [
            {
                'mrd_number': 'MRD001',
                'name': 'Ramesh Kumar',
                'age': '55',
                'sex': 'Male',
                'contact': '9876543210',
                'address': 'Mumbai, Maharashtra'
            },
            {
                'mrd_number': 'MRD002',
                'name': 'Priya Sharma',
                'age': '48',
                'sex': 'Female',
                'contact': '9876543211',
                'address': 'Delhi'
            },
            {
                'mrd_number': 'MRD003',
                'name': 'Suresh Patel',
                'age': '62',
                'sex': 'Male',
                'contact': '9876543212',
                'address': 'Gujarat'
            },
        ]
        
        patients = []
        for patient_data in patients_data:
            patient = Patient(
                doctor_id=user.id,
                **patient_data
            )
            db.session.add(patient)
            db.session.flush()
            patients.append(patient)
            print(f"✓ Created patient: {patient.name}")
        
        db.session.commit()
        
        print("\n5. Creating sample visits...")
        # Visit 1 for Ramesh Kumar
        visit1 = Visit(
            patient_id=patients[0].id,
            doctor_id=user.id,
            visit_type='New Visit',
            chief_complaints='Increased thirst and frequent urination for 2 months',
            height=170.0,
            weight=78.0,
            bmi=27.0,
            bp_systolic=140,
            bp_diastolic=90,
            pulse=82,
            temperature=98.6,
            spo2=98,
            history='Diagnosed with Type 2 Diabetes 10 years ago. Family history of diabetes.',
            examination='General: Well built, moderately nourished. CVS: S1 S2 normal. RS: Clear. Abdomen: Soft, non-tender.',
            diagnosis='Type 2 Diabetes Mellitus with Diabetic Nephropathy',
            comorbidities='Diabetic Nephropathy, Hypertension',
            investigation='HbA1c: 8.5%, eGFR: 45 ml/min, Creatinine: 1.8 mg/dl, Urine Albumin: 300 mg/24hr',
            follow_up_date=(datetime.now() + timedelta(days=30)).date(),
            follow_up_notes='Review HbA1c and kidney function. Adjust medications as needed.'
        )
        db.session.add(visit1)
        db.session.flush()
        print(f"✓ Visit for {patients[0].name}")
        
        # Visit 2 for Priya Sharma
        visit2 = Visit(
            patient_id=patients[1].id,
            doctor_id=user.id,
            visit_type='New Visit',
            chief_complaints='Fatigue and weight loss',
            height=162.0,
            weight=65.0,
            bmi=24.8,
            bp_systolic=120,
            bp_diastolic=80,
            pulse=76,
            temperature=98.4,
            spo2=99,
            history='Newly diagnosed Type 2 Diabetes. No significant past history.',
            examination='General: Well nourished. CVS: S1 S2 normal. RS: Clear. Per Abdomen: Soft, non-tender.',
            diagnosis='Type 2 Diabetes Mellitus',
            comorbidities='',
            investigation='HbA1c: 7.2%, FBS: 145 mg/dl, PPBS: 210 mg/dl, Lipid Profile: Within normal limits',
            follow_up_date=(datetime.now() + timedelta(days=90)).date(),
            follow_up_notes='Lifestyle modification, regular follow-up with HbA1c in 3 months.'
        )
        db.session.add(visit2)
        db.session.flush()
        print(f"✓ Visit for {patients[1].name}")
        
        # Visit 3 for Suresh Patel
        visit3 = Visit(
            patient_id=patients[2].id,
            doctor_id=user.id,
            visit_type='Follow-up',
            chief_complaints='Worsening breathlessness and pedal edema',
            height=168.0,
            weight=72.0,
            bmi=25.5,
            bp_systolic=150,
            bp_diastolic=95,
            pulse=88,
            temperature=98.5,
            spo2=96,
            history='Long-standing diabetes with multiple complications.',
            examination='General: Moderately built. CVS: S1 S2 normal, no murmurs. RS: Bilateral basal crepitations. Pedal edema present.',
            diagnosis='Type 2 Diabetes Mellitus with CKD Stage 4',
            comorbidities='Chronic Kidney Disease, Hypertension, Heart Failure',
            investigation='HbA1c: 9.2%, eGFR: 25 ml/min, BNP elevated, Echo: EF 40%',
            follow_up_date=(datetime.now() + timedelta(days=14)).date(),
            follow_up_notes='Urgent follow-up for kidney function monitoring. Consider nephrology referral.'
        )
        db.session.add(visit3)
        db.session.flush()
        print(f"✓ Visit for {patients[2].name}")
        
        db.session.commit()
        
        print("\n6. Creating sample prescriptions...")
        # Prescription for visit 1
        metformin = GenericDrug.query.filter_by(generic_name='Metformin').first()
        metformin_brand = BrandMedication.query.filter_by(generic_drug_id=metformin.id).first()
        
        prescription1 = Prescription(
            visit_id=visit1.id,
            brand_medication_id=metformin_brand.id,
            dosage='500mg',
            frequency='BD',
            timing='1-0-1',
            duration='30 days',
            instructions='Take after meals',
            warnings='Avoid in severe CKD (eGFR <30). Risk of lactic acidosis. Consider dose reduction in moderate CKD.'
        )
        db.session.add(prescription1)
        print(f"✓ Prescription for {patients[0].name}: {metformin_brand.brand_name}")
        
        # Prescription for visit 2
        sitagliptin = GenericDrug.query.filter_by(generic_name='Sitagliptin').first()
        sitagliptin_brand = BrandMedication.query.filter_by(generic_drug_id=sitagliptin.id).first()
        
        prescription2 = Prescription(
            visit_id=visit2.id,
            brand_medication_id=sitagliptin_brand.id,
            dosage='100mg',
            frequency='OD',
            timing='1-0-0',
            duration='30 days',
            instructions='Take before breakfast'
        )
        db.session.add(prescription2)
        print(f"✓ Prescription for {patients[1].name}: {sitagliptin_brand.brand_name}")
        
        db.session.commit()
        
        print("\n" + "="*60)
        print("✓ Sample data population complete!")
        print("="*60)
        print("\nLogin Credentials:")
        print(f"  Username: demo_doctor")
        print(f"  Password: password123")
        print("\nStatistics:")
        print(f"  - Generic Drugs: {GenericDrug.query.count()}")
        print(f"  - Brand Medications: {BrandMedication.query.count()}")
        print(f"  - Comorbidities: {Comorbidity.query.count()}")
        print(f"  - Drug-Comorbidity Interactions: {DrugComorbidityInteraction.query.count()}")
        print(f"  - Patients: {Patient.query.count()}")
        print(f"  - Visits: {Visit.query.count()}")
        print(f"  - Prescriptions: {Prescription.query.count()}")
        print("="*60)

if __name__ == '__main__':
    populate_sample_data()
