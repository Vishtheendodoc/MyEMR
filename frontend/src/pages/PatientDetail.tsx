import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, Appointment, Bill, ClinicProfile, LabResult, PatientDetail } from '../api/client';
import { latestLabRows } from '../utils/labResults';
import { useAuth } from '../hooks/useAuth';
import { formatClinicDate, formatClinicDateTime } from '../utils/clinicTime';
import { openPrintHtml } from '../utils/openPrintHtml';
import { printBillInvoice } from '../utils/printBill';

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [bills, setBills] = useState<Record<string, any>[]>([]);
  const [opened, setOpened] = useState<Bill | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);
  const [clinic, setClinic] = useState<ClinicProfile | null>(null);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [error, setError] = useState('');
  const showBills = user?.role === 'doctor' || user?.role === 'billing' || user?.role === 'pharmacy' || user?.role === 'admin';
  const showLabs = user?.role === 'doctor' || user?.role === 'nurse' || user?.role === 'admin';

  useEffect(() => {
    if (!id) return;
    api.patient(Number(id)).then(setPatient);
    api.patientAppointments(Number(id)).then(setAppointments).catch(() => setAppointments([]));
    if (showLabs) api.labs(Number(id)).then(setLabs).catch(() => setLabs([]));
    if (showBills) {
      api.patientBills(Number(id)).then(setBills).catch(() => setBills([]));
      api.clinicProfile().then(setClinic).catch(() => setClinic(null));
    }
  }, [id, showBills, showLabs]);

  const openBill = async (billId: number) => {
    setError('');
    setOpeningId(billId);
    try {
      setOpened(await api.bill(billId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open this invoice');
    } finally {
      setOpeningId(null);
    }
  };

  const money = (value: number) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (!patient) return <div className="text-center py-5 text-muted">Loading patient…</div>;

  const hasVisits = patient.visits.length > 0;
  const reload = () => {
    if (!id) return;
    api.patient(Number(id)).then(setPatient);
    api.patientAppointments(Number(id)).then(setAppointments).catch(() => setAppointments([]));
  };

  const appointmentLabel = (item: Appointment) => {
    if (item.registration_status === 'cancelled') return 'Registration cancelled';
    if (item.status === 'cancelled') return 'Appointment cancelled';
    if (item.status === 'arrived') return 'Waiting';
    if (item.status === 'in_consult') return 'In consult';
    if (item.status === 'completed') return 'Done';
    if (item.status === 'scheduled') return 'Booked';
    return item.status;
  };

  const cancelAppointment = async (item: Appointment) => {
    if (!window.confirm(`Cancel the appointment for ${patient.name}? The registration and MRD stay.`)) return;
    setError('');
    try {
      await api.updateAppointmentStatus(item.id, 'cancelled');
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel this appointment');
    }
  };

  const cancelChart = async () => {
    if (!window.confirm(`Cancel the registration for ${patient.name}?`)) return;
    setError('');
    try {
      await api.cancelRegistration(patient.id);
      navigate('/patients');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel this registration');
    }
  };

  return (
    <div>
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="page-header">
        <div>
          <h2>{patient.name}</h2>
          <p className="page-subtitle">
            {patient.mrd_number
              ? `${(patient.mrd_number.startsWith('TMP-') || patient.registration_status === 'temporary') ? 'Temp id' : 'MRD'} ${patient.mrd_number}`
              : 'No MRD'} · {patient.age} · {patient.sex}
          </p>
        </div>
        <div className="d-flex gap-2 flex-wrap">
          {(patient.mrd_number || '').startsWith('TMP-') && (
            <Link to={`/patients/${patient.id}/edit`} className="btn btn-primary">Register and assign MRD</Link>
          )}
          <Link to={`/patients/${patient.id}/edit`} className="btn btn-outline-secondary">
            <i className="fas fa-pen me-1"></i>Edit
          </Link>
          <button type="button" className="btn btn-outline-secondary" onClick={() => {
            const esc = (value: string) => value.replace(/[&<>]/g, ch => ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : '&gt;');
            const visits = patient.visits.map(v => `<li>${esc(String(v.visit_date))} · ${esc(v.visit_type)}${v.diagnosis ? ` · ${esc(v.diagnosis)}` : ''}</li>`).join('') || '<li>None</li>';
            const results = latestLabRows(labs).map(lab => `<li>${esc(lab.test_name)}: ${esc(lab.value)} ${esc(lab.unit || '')} (${esc(lab.result_date.slice(0, 10))})</li>`).join('') || '<li>None</li>';
            openPrintHtml(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(patient.name)}</title><style>body{font-family:sans-serif;padding:24px}h1{font-size:22px}</style></head><body><h1>${esc(patient.name)}</h1><p>${esc(patient.age)} · ${esc(patient.sex)} · ${esc(patient.mrd_number || 'No MRD')}</p><p><strong>Allergies:</strong> ${esc(patient.allergies || 'Not recorded')}</p><h2>Latest results</h2><ul>${results}</ul><h2>Visits</h2><ul>${visits}</ul></body></html>`);
          }}>Print summary</button>
          <button type="button" className="btn btn-outline-danger" onClick={cancelChart}>Cancel registration</button>
          <Link to={`/patients/${patient.id}/visits/new`} className="btn btn-primary">
            <i className={`fas ${hasVisits ? 'fa-redo' : 'fa-plus'} me-1`}></i>
            {hasVisits ? 'Create Revisit' : 'New Visit'}
          </Link>
        </div>
      </div>

      <div className="card patient-hero mb-4">
        <div className="row g-3 position-relative" style={{ zIndex: 1 }}>
          <div className="col-md-3">
            <div className="text-muted small">MRD</div>
            <strong>{patient.mrd_number || '—'}</strong>
          </div>
          <div className="col-md-2">
            <div className="text-muted small">Age</div>
            <strong>{patient.age}</strong>
          </div>
          <div className="col-md-2">
            <div className="text-muted small">Sex</div>
            <strong>{patient.sex}</strong>
          </div>
          <div className="col-md-5">
            <div className="text-muted small">Contact</div>
            <strong>{patient.contact || '—'}</strong>
          </div>
          <div className="col-12">
            <div className="text-muted small">Address</div>
            <strong>{patient.address || '—'}</strong>
          </div>
          {(patient.allergies?.trim() || patient.problem_list?.trim()) && (
            <div className="col-12">
              <div className="alert alert-warning mb-0 py-2">
                {patient.allergies?.trim() && <div><strong>Allergies:</strong> {patient.allergies}</div>}
                {patient.problem_list?.trim() && <div><strong>Problem list:</strong> {patient.problem_list}</div>}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="row g-3 mb-4">
        {[
          ...(showLabs
            ? [
                ...(user?.role === 'doctor'
                  ? [{ to: `/patients/${patient.id}/360`, icon: 'id-card', title: 'Patient 360', desc: 'Longitudinal chart' }]
                  : []),
                { to: `/patients/${patient.id}/observations`, icon: 'notes-medical', title: 'Observations', desc: 'Structured results' },
                { to: `/patients/${patient.id}/intelligence`, icon: 'stethoscope', title: 'Clinical review', desc: 'Versioned prompts' },
                { to: `/patients/${patient.id}/timeline`, icon: 'chart-line', title: 'Timeline', desc: 'Vitals & trends' },
                { to: `/patients/${patient.id}/labs`, icon: 'flask', title: 'Labs & Imaging', desc: 'Results & reports' },
                { to: `/patients/${patient.id}/diabetes`, icon: 'tint', title: 'Diabetes', desc: 'HbA1c, CGM, screening' },
                { to: `/patients/${patient.id}/growth`, icon: 'child', title: 'Growth Chart', desc: 'Pediatric growth' },
                { to: `/patients/${patient.id}/medication-safety`, icon: 'pills', title: 'Medication safety', desc: 'Checks without changes' },
              ]
            : []),
        ].map(item => (
          <div className="col-md-3" key={item.to}>
            <Link to={item.to} className="card hub-link">
              <div className="hub-icon"><i className={`fas fa-${item.icon}`}></i></div>
              <div>
                <strong>{item.title}</strong>
                <span>{item.desc}</span>
              </div>
            </Link>
          </div>
        ))}
      </div>

      {showLabs && (
        <div className="card mb-4">
          <div className="card-header d-flex justify-content-between align-items-center">
            <h5 className="mb-0">Latest results</h5>
            <Link to={`/patients/${patient.id}/labs`}>Labs & imaging</Link>
          </div>
          {latestLabRows(labs).length === 0 ? (
            <div className="p-3 text-muted">No results stored yet.</div>
          ) : (
            <div className="table-responsive">
              <table className="table mb-0">
                <thead><tr><th>Test</th><th>Value</th><th>Date</th></tr></thead>
                <tbody>
                  {latestLabRows(labs).map(lab => (
                    <tr key={lab.id}>
                      <td>{lab.test_name}</td>
                      <td>{lab.value} {lab.unit || ''}</td>
                      <td>{lab.result_date.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {showBills && (
        <div className="card mb-4">
          <div className="card-header"><h5 className="mb-0">Billing history</h5></div>
          <div className="table-responsive">
            <table className="table mb-0">
              <thead><tr><th>Date</th><th>Invoice</th><th>Type</th><th>Total</th><th>Paid</th><th>Due</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {bills.length === 0 ? (
                  <tr><td colSpan={8} className="text-muted text-center py-3">No invoices yet</td></tr>
                ) : bills.map(bill => (
                  <tr key={bill.id}>
                    <td>{formatClinicDate(bill.created_at)}</td>
                    <td>{bill.invoice_number || bill.id}</td>
                    <td>{bill.bill_type || '—'}</td>
                    <td>₹{Number(bill.amount || 0).toLocaleString('en-IN')}</td>
                    <td>₹{Number(bill.amount_paid || 0).toLocaleString('en-IN')}</td>
                    <td>₹{Number(bill.outstanding || 0).toLocaleString('en-IN')}</td>
                    <td>{bill.payment_status}</td>
                    <td className="text-end">
                      <button type="button" className="btn btn-sm btn-outline-primary" disabled={openingId === bill.id} onClick={() => openBill(bill.id)}>
                        {openingId === bill.id ? 'Opening…' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {opened && (
            <div className="border-top p-3">
              <div className="d-flex justify-content-between align-items-start gap-2 mb-3">
                <div>
                  <h5 className="mb-1">{opened.invoice_number || `Invoice ${opened.id}`}</h5>
                  <div className="text-muted small">
                    {formatClinicDateTime(opened.created_at)} · {opened.bill_type || opened.category || 'Invoice'} · {opened.payment_status}
                    {opened.credit_note_number ? ` · Credit note ${opened.credit_note_number}` : ''}
                  </div>
                </div>
                <div className="d-flex gap-2">
                  <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => printBillInvoice(opened, clinic?.name || 'Endo Clinic', user?.doctor_name, clinic || undefined)}>Print</button>
                  <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setOpened(null)}>Close</button>
                </div>
              </div>
              <div className="table-responsive">
                <table className="table table-sm mb-3">
                  <thead><tr><th>Item</th><th>Qty</th><th>Rate</th><th>GST</th><th className="text-end">Amount</th></tr></thead>
                  <tbody>
                    {(opened.line_items && opened.line_items.length ? opened.line_items : [{
                      description: opened.description,
                      quantity: 1,
                      rate: opened.base_amount ?? opened.amount,
                      gst_percent: opened.gst_percent || 0,
                      base_amount: opened.base_amount ?? opened.amount,
                      gst_amount: opened.gst_amount || 0,
                    }]).map((line, index) => (
                      <tr key={`${line.description}-${index}`}>
                        <td>
                          {line.description}
                          {line.note ? <div className="small text-muted">{line.note}</div> : null}
                        </td>
                        <td>{line.quantity ?? 1}</td>
                        <td>{money(line.rate || line.base_amount || 0)}</td>
                        <td>{line.gst_percent || 0}%</td>
                        <td className="text-end">{money((line.base_amount || 0) + (line.gst_amount || 0))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="row g-2">
                <div className="col-md-6">
                  <div className="small text-muted mb-1">Payments</div>
                  {(opened.receipts && opened.receipts.length > 0) ? (
                    <ul className="mb-0">
                      {opened.receipts.map((receipt, index) => (
                        <li key={`${receipt.method}-${index}`}>{receipt.method} · {money(receipt.amount)}{receipt.kind && receipt.kind !== 'collection' ? ` · ${receipt.kind.replace('_', ' ')}` : ''}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>{opened.payment_method || 'No payment recorded'} · {money(opened.amount_paid || 0)}</div>
                  )}
                </div>
                <div className="col-md-6">
                  <table className="table table-sm mb-0">
                    <tbody>
                      <tr><td>Discount</td><td className="text-end">{money(opened.discount_amount || 0)}</td></tr>
                      <tr><td>GST</td><td className="text-end">{money(opened.gst_amount || 0)}</td></tr>
                      {(opened.round_off || 0) !== 0 && <tr><td>Round off</td><td className="text-end">{money(opened.round_off || 0)}</td></tr>}
                      <tr><td>Total</td><td className="text-end fw-semibold">{money(opened.amount)}</td></tr>
                      <tr><td>Paid</td><td className="text-end">{money(opened.amount_paid || 0)}</td></tr>
                      <tr><td>Due</td><td className="text-end">{money(Math.max(0, opened.amount - (opened.amount_paid || 0)))}</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card mb-4">
        <div className="card-header"><h5 className="mb-0">Appointments</h5></div>
        <div className="table-responsive">
          <table className="table mb-0">
            <thead><tr><th>When</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {appointments.length === 0 ? (
                <tr><td colSpan={3} className="text-muted text-center py-3">No appointments</td></tr>
              ) : appointments.map(item => {
                const closed = item.status === 'cancelled' || item.registration_status === 'cancelled';
                const canCancel = !closed && (user?.role === 'registration' ? item.status === 'scheduled' : item.status !== 'completed');
                return (
                  <tr key={item.id} className={closed ? 'text-muted' : undefined}>
                    <td>{formatClinicDateTime(item.scheduled_at)}</td>
                    <td>{appointmentLabel(item)}</td>
                    <td className="text-end">
                      {canCancel && (
                        <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => cancelAppointment(item)}>Cancel appointment</button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Visit History</h5>
          <span className="badge badge-soft">{patient.visits.length} visit{patient.visits.length === 1 ? '' : 's'}</span>
        </div>
        <div className="table-responsive">
          {user?.role !== 'doctor' ? (
            <p className="p-3 mb-0 text-muted">Visit notes stay on the doctor chart.</p>
          ) : (
          <table className="table mb-0">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Complaints</th>
                <th>Diagnosis</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {patient.visits.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center text-muted py-4">
                    No visits yet. Start the first visit to open the case sheet.
                  </td>
                </tr>
              ) : patient.visits.map(v => (
                <tr key={v.id}>
                  <td>{formatClinicDate(v.visit_date)}</td>
                  <td>
                    <span className="badge badge-soft">{v.visit_type}</span>
                    {v.status === 'cancelled' && <span className="badge bg-secondary ms-1">Appointment cancelled</span>}
                  </td>
                  <td>{v.chief_complaints || '—'}</td>
                  <td>{v.diagnosis || '—'}</td>
                  <td className="text-end">
                    <Link to={`/visits/${v.id}`} className="btn btn-sm btn-outline-primary">View</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </div>
      </div>
    </div>
  );
}
