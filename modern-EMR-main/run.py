from app import app

if __name__ == '__main__':
    with app.app_context():
        from models import db
        from pdf_service import ensure_visit_pdf_columns
        from prescription_utils import ensure_prescription_columns
        from user_utils import ensure_user_columns
        from medication_service import split_semaglutide_range_brands, sync_medication_template
        db.create_all()
        ensure_visit_pdf_columns()
        ensure_prescription_columns()
        ensure_user_columns()
        split_semaglutide_range_brands()
        sync_medication_template()
    app.run(host='0.0.0.0', port=5000, debug=True)
