# Development status

## Phase: Modules 1–10

Status: implemented and checked on 13 Nov 2026.

## What is in place

Modules 1 and 2 remain as previously delivered: Patient 360 and structured clinical observations.

### Module 3 — Clinical review prompts

A doctor opens **Clinical review** on a patient chart. The service reads stored observations and the versioned rows in `clinical_rule`. Each open prompt has a title, explanation, triggering values, earlier values, a suggested review, a guideline citation, severity, and the rule version. The doctor can acknowledge it or dismiss it with a reason. Running the check again updates the same open prompt instead of adding another copy. A prompt closes itself when the latest stored value no longer meets the rule.

The wording asks for a review. It does not assign a diagnosis or change a medicine. A single HbA1c of 7.4% does not open the high HbA1c prompt. The existing visit CDS endpoint is unchanged.

### Module 4 — Diabetes and CGM

The diabetes screen keeps the HbA1c chart, glucose trace, and insulin dose table. It now also shows, for a configurable period of 1–90 days (default 14):

- Time in range, time above range, and time below range, using 70–180 mg/dL
- GMI from `3.31 + 0.02392 × mean glucose`
- Coefficient of variation, average glucose, and standard deviation
- An hourly profile, a daily profile, nocturnal readings below 70 mg/dL from 00:00–06:00 Asia/Kolkata, and clock-window glucose averages
- Insulin basal and bolus totals, units per kilogram when a weight is stored, dose change between visits, SGLT2 and GLP-1 names, and overdue screening prompts when diabetes is recorded

Meal times are not stored, so the post-meal figures are clock windows.

### Module 5 — Follow-up plans and recall

Removed on 13 Nov 2026. The Recall screen, its API, and the `patient_care_plan` and `monitoring_schedule` tables are gone. Visit follow-up dates and the Follow-ups list are unchanged.

### Module 6 — Medication safety

The medication safety screen compares the latest prescription with the one before it. It reports duplicate molecules, a small editable drug-pair list, the existing comorbidity warnings, a renal-dose prompt when eGFR is below 45, allergy text matches, medicines that disappeared, refill durations, and pharmacy-bill text from the last 90 days. Brand substitution can be requested and approved. Approval is audited and does not change the prescribed product. New and deleted prescriptions are audited.

### Module 7 — Assistant

Removed on 13 Nov 2026. The screen, API, and assistant tables are gone. Visit notes, prescriptions, and observations were left in place.

### Module 8 — Research export

Removed on 18 Nov 2026. The screen, API, and research tables are gone. Charts and bills were left in place.

### Module 9 — Practice analytics

The analytics screen keeps the previous totals and adds separate consultation, pharmacy, and laboratory amounts. A bill is placed in one bucket from its category. Purchase cost is not stored, so pharmacy gross margin is empty. The screen also shows average HbA1c against a general 7% adult reference, screening coverage, thyroid and bone follow-up coverage, weight loss of at least 1 kg, visit counts, new and returning patients, expiring stock, and follow-up conversion.

### Module 10 — Sessions and access

Refresh tokens now carry an id stored in `refresh_session`. Refresh rotates that id and rejects the previous token. Logout revokes it. Login allows 30 attempts per email per minute in the current API process. Laboratory results, imaging, the timeline, the diabetes screen, growth, visit CDS, and analytics are limited to the doctor. Registration can still open the patient chart; diagnosis and complaint text are blank on that response. The chart page hides visit notes from desk roles. A partial FHIR Patient read exists for the doctor and is marked as not a certified FHIR, ABDM, SNOMED, or LOINC interface. `GET /interop/status` reports those integrations as not configured. SQLite backup and restore copy is covered by `scripts/backup_sqlite.py` and a round-trip test.

## Database

Alembic revision `004` (`003` → `004`) creates the platform tables when they are missing, then inserts the default rules and drug pairs. Revision `005` drops the clinical assistant tables. Revision `006` drops the recall tables. Revision `007` drops the research tables. Revision `008` adds suppliers, the medicine catalogue, the inventory ledger, purchases, bill payments, and returns. The live clinic database is updated on startup and must not be migrated with `alembic upgrade head`.

```bash
cd backend
alembic upgrade head
```

Startup still calls `create_all()` and then inserts any missing default rows.

New tables: `clinical_rule`, `clinical_alert`, `drug_pair_interaction`, `substitution_request`, `refresh_session`, `supplier`, `medicine_item`, `inventory_txn`, `purchase_invoice`, `purchase_line`, `bill_payment`, `sales_return`, `sales_return_line`, `purchase_return`, `purchase_return_line`.

## Checks

- Platform tests passed: alert identity, moderate HbA1c, dismiss reason, CGM range math, medication checks without changing the prescription, separate revenue buckets, refresh reuse, doctor-only labs, FHIR wording, SQLite restore, and Alembic through `008`.
- Commerce tests passed: purchase stock and duplicate invoice refusal, expired-stock block, damaged return quarantine, split cash and UPI collections, and the cash drawer on day close.
- Observation tests passed, including upgrade from `002` to head.
- Patient 360 tests passed.
- Smoke test passed.
- Frontend production build passed.
- There is no frontend test runner in this project. `pytest` is not installed; the test modules were executed directly.

## Configuration

No new environment variable is required.

## Remaining limitations

- Patient 360 still reads the original lab, visit, and CGM tables.
- Imaging is not an observation. Calculated eGFR is still computed on Patient 360 and is not stored unless an eGFR result was entered.
- Purchase rate is stored on each batch. The analytics screen still does not calculate pharmacy margin.
- One invoice can record two payment modes. A third mode is entered as another collection.
- The tax split follows the rate stored on each line and the clinic tax setting. It is bookkeeping, not a filed GST return.
- While a day is still open, extra lines for that visit are added to its invoice, and that merged invoice stays in the consultation bucket. After the day is closed, a later pharmacy or lab sale opens a new invoice. An outstanding balance can still be collected; that receipt is counted on the day the money is received, and the locked day keeps the figures it had when it was closed.
- Visit detail itself is still available to any signed-in role. Desk roles no longer receive diagnosis text on the patient summary, and they cannot open labs, timeline, diabetes, growth, or CDS.
- The FHIR Patient read, ABDM, SNOMED CT, and LOINC entries are not certifications.
- The smoke-test migrate dry run still looks for a script path that is not in `backend/tests`. That predates this work.
- Restart the API after this upgrade so it loads the new routes. If port 8000 stays occupied by an old process, stop that process first.
