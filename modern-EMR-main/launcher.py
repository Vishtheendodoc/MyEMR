"""Desktop launcher - starts the EMR server and opens the browser."""
import threading
import time
import webbrowser

from app import app

APP_URL = 'http://127.0.0.1:5000'


def open_browser():
    time.sleep(1.5)
    webbrowser.open(APP_URL)


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

    print('Endocrinology EMR is starting...')
    print(f'Open in browser: {APP_URL}')
    print('Close this window to stop the server.\n')

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
