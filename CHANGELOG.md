# Changelog

## 2026-11-21 — Lab results stay on the chart

A result entered on a visit, on the labs page, or as an observation is the same result on the chart, the diabetes page, the timeline, and the printed summary. Saving the visit again updates that result instead of adding another copy.

## 2026-11-21 — Endocrine clinics, nurse access, and chart tools

Visit templates now cover diabetic foot, gestational diabetes, pediatric endocrine care, and obesity, and the bone template adds DXA Z-score, FRAX, fractures, and drug holiday. The chart has tabs, a print summary, saved note snippets, family history, and a consent note. The dashboard shows overdue follow-ups. A nurse can chart but cannot prescribe or open billing. The session signs out after 20 idle minutes, and a dark theme is available. ABDM and ABHA stay unconnected.

## 2026-11-21 — Chart banner and patient search

The chart keeps the patient name, MRD, and allergies in view. Search from Ctrl+K finds a patient by name, phone, or MRD. Switching the desk doctor no longer stops on a missing value.

## 2026-11-20 — Appointment cancel matches the chart

Cancelling an appointment from the schedule also closes that day’s visit. The patient page shows the same appointment and can cancel it there.

## 2026-11-20 — Cancelled registration frees the MRD

Cancelling a registration releases that MRD so the next chart can use it. Cancelling an appointment leaves the registration and the MRD in place, and the two show as different statuses.

## 2026-11-20 — Pharmacy can decline a dispense

Pharmacy can leave a note and decline a prescription when the patient does not buy the medicines at the clinic. Stock is left unchanged.

## 2026-11-20 — Registration search includes every doctor

The registration desk can search patients from every doctor. Registering the person found assigns that visit to the doctor chosen on the row.

## 2026-11-20 — Registration chooses the doctor

The registration desk picks the doctor while registering a patient. The chart and today’s visit are filed under that doctor.

## 2026-11-20 — Each doctor has a separate setup

Registering a doctor creates that doctor’s own letterhead and price list. Pharmacy, billing, and registration choose which doctor they are viewing, billing, and dispensing for.

## 2026-11-20 — Follow-ups, the calendar, and reminders stay together

Marking a follow-up done on the calendar shows it as done. Moving that calendar slot moves the follow-up date. Overdue follow-ups appear on Reminders, which is where Revisit, Schedule, and WhatsApp now live.

## 2026-11-20 — A cancelled calendar follow-up shows on Follow-ups

Cancelling a follow-up from the Schedule calendar marks that follow-up cancelled. It leaves the upcoming and overdue lists.

## 2026-11-20 — Clinic messages stay off the reminder log

A message sent to all patients from Messages is not listed in the reminder log. That log keeps appointment and follow-up reminders.

## 2026-11-20 — Reminder names and cancel

A reminder can be cancelled so it is not sent. The clinic name and doctor name in the message can be changed on the Reminders page.

## 2026-11-20 — Cancelled registration leaves the waiting list

Cancelling a registration marks today’s consultation as cancelled. It no longer stays on the waiting list.

## 2026-11-20 — Open a saved invoice

Billing history keeps every invoice. View opens the saved items, tax, and payments, and the invoice can be printed again.

## 2026-11-20 — Doctor profile fields

Qualifications and the KMC number are shown only on a doctor's profile. Desk logins keep a display name.

## 2026-11-20 — Register a returning patient, and clinic WhatsApp

The registration screen searches old charts by name, MRD, or mobile and registers that visit. Messages can send a greeting, a note, or the video file itself in WhatsApp. Extra names and mobile numbers can be saved and used again. A mobile already on a chart or on that list cannot be entered a second time. A test list holds private numbers so a message can be tried before it goes to registered patients. One click sends that message in each WhatsApp chat on the chosen list.

## 2026-11-19 — MRD numbers and cancelling a booking

A booking made before the patient arrives keeps a temporary id, TMP-year-serial. Registration at the desk, or sending them to the doctor, assigns the next permanent MRD for that year. That number is not used again. An appointment can be cancelled from the day list or the upcoming list. A registration can be cancelled until a prescription is printed or the visit is locked and finalised.

## 2026-11-19 — Registration joins today’s queue

Registering a patient sends them to the doctor as waiting, marked New or Revisit and Walk-in, In clinic, or Online. Someone registered earlier today is already on that list. The doctor consults that visit; ordered tests go to billing and prescriptions go to pharmacy.

## 2026-11-19 — Doctor home queue

The doctor’s home screen opens on today’s consultation list. Each row shows the time, whether the patient is new or a revisit, and whether they are a walk-in, an online booking, or an in-clinic appointment.

## 2026-11-18 — Open a locked day

A doctor or admin can open a locked day from Day close, or from the billing message that says the day is locked. The billing and pharmacy desks cannot open it.

## 2026-11-18 — Receipt after day close

Collecting an outstanding balance after day close is recorded on the day the money arrives. The locked day keeps the totals it had when it was closed. Cancelling or changing that invoice still needs the day to be re-opened.

## 2026-11-18 — Split collections and the cash drawer

An invoice can take cash and UPI, or any two modes, as separate payment rows. Day close stores the opening cash and the counted closing cash, and lists bank transfer on its own. The pharmacy window names the earliest-expiring saleable batch and keeps a substitution note on that line.

## 2026-11-18 — Billing, pharmacy stock, and finance

Purchases, supplier invoices, batch stock, and returns now write an inventory ledger. A sale after day close still opens its own invoice. Finance shows collections by service and payment mode. GST on an invoice is split from the rate already stored on each line. Expired stock cannot be dispensed. Damaged returns go to quarantine. Completed invoices are cancelled or credited, not deleted.

## 2026-11-18 — Research removed

The Research screen, its API, and the `research_ethics`, `research_consent`, and `research_subject` tables are removed. Alembic revision `007` drops those tables. Charts, prescriptions, and bills are unchanged.

## 2026-11-18 — Pharmacy bill after a closed day

A medicine bill raised after day close opens a new invoice. It no longer tries to change the locked visit invoice, and the reason for a failed save is shown inside the dispense window.

## 2026-11-13 — Recall removed

The Recall screen, its API, and the `patient_care_plan` and `monitoring_schedule` tables are removed. Alembic revision `006` drops those tables. Visit follow-up dates and the Follow-ups list are unchanged.

## 2026-11-13 — Clinical assistant removed

The clinical assistant screen, its API, and the `ai_consent`, `ai_request_log`, and `ai_draft` tables are removed. Alembic revision `005` drops those tables. Visit notes, prescriptions, and observations are unchanged. The optional `AI_*` settings are no longer used.

## 2026-11-13 — Modules 3 to 10

Added versioned clinical review prompts, CGM summaries on the diabetes screen, medication safety checks that do not rewrite prescriptions, a de-identified research export, separate consultation, pharmacy, and laboratory analytics, and rotating refresh tokens. The clinical assistant and the recall list added in this batch were removed the same day.

- Alembic revision `004` adds the new tables and the default rules, schedules, and drug-pair prompts.
- Doctor-only routes live under `/api/v1` for intelligence, medication safety, research, interoperability status, and a partial FHIR Patient read.
- Laboratory, imaging, timeline, diabetes, growth, visit CDS, and analytics responses are limited to the doctor. Existing lab and visit response shapes are otherwise unchanged.
- Screens: Clinical review, Medication safety, and Research. Diabetes and Analytics show the new figures.

## 2026-11-13 — Structured clinical observations

Added a `clinical_observation` record for laboratory results, CGM readings, and visit measurements, plus doctor entry for manual, imported, and unverified report extracts.

- Alembic revision `003` creates the table when needed and backfills existing rows without copying the same source twice.
- `GET` and `POST /api/v1/patients/{patient_id}/observations`, and `POST /api/v1/observations/{observation_id}/verify`, are doctor-only.
- New screen at `/patients/:id/observations`.
- Existing lab, visit, CGM, and Patient 360 API responses are unchanged.

No new environment variables.

## 2026-11-13 — Patient 360

Added a doctor-only longitudinal chart for an existing patient. It reads current patients, visits, prescriptions, labs, imaging, CGM readings, bills, and appointments. It does not add tables or change records.

- `GET /api/v1/patients/{patient_id}/patient-360` requires the doctor role.
- New screen at `/patients/:id/360`, linked from the patient chart for doctors.
- Desk roles are blocked from that path in the existing role map.
- Each view is written to the audit log as `patient.view_360`.

No Alembic migration. No new environment variables.
