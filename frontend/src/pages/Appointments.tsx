import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, Appointment, Patient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { openPrintHtml } from '../utils/openPrintHtml';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function toLocalInputValue(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function PatientSearch({
  patients, patientId, query, open, onQuery, onOpen, onPick,
}: {
  patients: Patient[];
  patientId: string;
  query: string;
  open: boolean;
  onQuery: (value: string) => void;
  onOpen: (open: boolean) => void;
  onPick: (id: string) => void;
}) {
  const selected = patients.find(p => String(p.id) === patientId);
  const q = query.trim().toLowerCase();
  const matches = q
    ? patients.filter(p =>
      p.name.toLowerCase().includes(q)
      || (p.mrd_number || '').toLowerCase().includes(q)
      || (p.contact || '').includes(q),
    ).slice(0, 8)
    : [];
  const exact = q ? patients.some(p => p.name.trim().toLowerCase() === q) : false;
  return (
    <div className="mb-2 position-relative">
      <input
        className="form-control"
        placeholder="Name, MRD, or mobile — or type a new name"
        required={!patientId}
        value={selected && !open ? `${selected.name}${selected.mrd_number ? ` (${selected.mrd_number})` : ''}` : query}
        onFocus={() => onOpen(true)}
        onChange={e => onQuery(e.target.value)}
      />
      {open && q && (
        <div className="list-group position-absolute w-100 shadow-sm" style={{ zIndex: 20, maxHeight: 240, overflow: 'auto' }}>
          {matches.map(p => (
            <button
              type="button"
              key={p.id}
              className="list-group-item list-group-item-action py-2"
              onClick={() => onPick(String(p.id))}
            >
              <div className="fw-semibold">{p.name}</div>
              <div className="small text-muted">{[p.mrd_number, p.contact].filter(Boolean).join(' · ') || 'No MRD'}</div>
            </button>
          ))}
          {!exact && (
            <button
              type="button"
              className="list-group-item list-group-item-action py-2"
              onClick={() => onOpen(false)}
            >
              <div className="fw-semibold">Book “{query.trim()}” as a new patient</div>
              <div className="small text-muted">A temporary id is kept until they register at the desk.</div>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function Appointments() {
  const { user } = useAuth();
  const isRegistration = user?.role === 'registration';
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string>(today.toISOString().slice(0, 10));
  const [dayCounts, setDayCounts] = useState<Record<string, number>>({});
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [form, setForm] = useState({ patient_id: '', scheduled_at: '', duration_minutes: '15', notes: '', channel: 'in_clinic', contact: '', age: '', sex: 'Other' });
  const [patientQuery, setPatientQuery] = useState('');
  const [patientOpen, setPatientOpen] = useState(false);
  const [autoSend, setAutoSend] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = () => {
    api.appointments().then(setAppts);
    api.patients().then(setPatients);
    api.appointmentCalendar(viewYear, viewMonth).then(data => {
      const map: Record<string, number> = {};
      data.days.forEach(d => { map[d.date] = d.count; });
      setDayCounts(map);
    });
  };

  useEffect(() => { load(); }, [viewYear, viewMonth]);
  useEffect(() => {
    api.remindersStatus().then(s => setAutoSend(s.auto_send_available)).catch(() => {});
  }, []);

  const calendarCells = useMemo(() => {
    const first = new Date(viewYear, viewMonth - 1, 1);
    const startPad = first.getDay();
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
    const cells: { date: Date | null; key: string }[] = [];
    for (let i = 0; i < startPad; i++) cells.push({ date: null, key: `pad-${i}` });
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ date: new Date(viewYear, viewMonth - 1, d), key: `d-${d}` });
    }
    return cells;
  }, [viewYear, viewMonth]);

  const dayAppts = useMemo(
    () => appts
      .filter(a => a.scheduled_at.startsWith(selectedDate))
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)),
    [appts, selectedDate],
  );
  const openDay = dayAppts.filter(a => a.status !== 'cancelled');
  const cancelledDay = dayAppts.filter(a => a.status === 'cancelled');

  const upcoming = useMemo(
    () => appts.filter(a => a.status === 'scheduled' && new Date(a.scheduled_at) >= new Date(today.toDateString())),
    [appts],
  );

  const prevMonth = () => {
    if (viewMonth === 1) { setViewYear(y => y - 1); setViewMonth(12); }
    else setViewMonth(m => m - 1);
  };

  const nextMonth = () => {
    if (viewMonth === 12) { setViewYear(y => y + 1); setViewMonth(1); }
    else setViewMonth(m => m + 1);
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      let patientId = Number(form.patient_id);
      if (!patientId) {
        const name = patientQuery.trim();
        if (!name) {
          setError('Type the patient name, or pick someone already registered.');
          return;
        }
        const already = patients.find(p => p.name.trim().toLowerCase() === name.toLowerCase());
        if (already) {
          setError(`${already.name} is already on the register${already.mrd_number ? ` (${already.mrd_number})` : ''}. Pick that name from the list.`);
          return;
        }
        const digits = form.contact.replace(/\D/g, '');
        if (digits && digits.length !== 10) {
          setError('Mobile number must be 10 digits, or leave it blank.');
          return;
        }
        const created = await api.createPatient({
          name,
          age: form.age.trim() || '—',
          sex: form.sex || 'Other',
          contact: digits || null,
          mrd_number: null,
          address: null,
          allergies: null,
          problem_list: null,
          temporary: true,
        });
        patientId = created.id;
      }
      await api.createAppointment({
        patient_id: patientId,
        scheduled_at: new Date(form.scheduled_at).toISOString(),
        duration_minutes: Number(form.duration_minutes),
        notes: form.notes || null,
        channel: form.channel,
      });
      setForm({ patient_id: '', scheduled_at: '', duration_minutes: '15', notes: '', channel: 'in_clinic', contact: '', age: '', sex: 'Other' });
      setPatientQuery('');
      setPatientOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule');
    }
  };

  const saveVitals = async (a: Appointment) => {
    const bp = (document.getElementById(`bp-${a.id}`) as HTMLInputElement | null)?.value || '';
    const [sys, dia] = bp.split('/').map(part => Number(part));
    const pulse = Number((document.getElementById(`pulse-${a.id}`) as HTMLInputElement | null)?.value);
    const weight = Number((document.getElementById(`wt-${a.id}`) as HTMLInputElement | null)?.value);
    await api.updateAppointment(a.id, {
      bp_systolic: sys || null,
      bp_diastolic: dia || null,
      pulse: pulse || null,
      weight: weight || null,
    });
    await load();
  };

  const printToken = (a: Appointment) => {
    openPrintHtml(`<!doctype html><html><body style="font-family:Segoe UI,Arial,sans-serif;text-align:center;padding:28px">
      <h2 style="margin-bottom:4px">Token ${a.token_number || ''}</h2>
      <div style="font-size:22px;font-weight:700">${a.patient_name || ''}</div>
      <div>${a.patient_mrd || ''}</div>
      <div style="margin-top:8px">${new Date(a.scheduled_at).toLocaleString('en-IN')}</div>
      <script>window.onload=function(){setTimeout(function(){window.print()},200)}</script>
    </body></html>`);
  };

  const remind = async (a: Appointment, auto = false) => {
    if (!a.patient_contact) {
      setError(`${a.patient_name} has no phone number.`);
      return;
    }
    setBusyId(a.id);
    setError('');
    try {
      const res = await api.sendReminder({
        source_type: 'appointment',
        source_id: a.id,
        auto_send: auto,
      });
      if (!auto && res.whatsapp_url) window.open(res.whatsapp_url, '_blank', 'noopener,noreferrer');
      if (auto && res.status === 'failed') setError(res.error || 'Auto-send failed');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reminder failed');
    } finally {
      setBusyId(null);
    }
  };

  const printDay = () => {
    const rows = openDay.map(a => `
      <tr>
        <td>${new Date(a.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
        <td>${a.patient_name || '—'}</td>
        <td>${a.patient_mrd || '—'}</td>
        <td>${a.patient_contact || '—'}</td>
        <td>${a.duration_minutes} min</td>
        <td>${a.notes || '—'}</td>
      </tr>`).join('');
    openPrintHtml(`<!doctype html><html><head><meta charset="utf-8"><title>Schedule ${selectedDate}</title>
      <style>
        body{font-family:Segoe UI,Arial,sans-serif;padding:24px}
        table{width:100%;border-collapse:collapse} th,td{border:1px solid #ccc;padding:8px;text-align:left;font-size:13px}
        th{background:#f3f7f8}
        @media print{button{display:none}}
      </style></head><body>
      <button onclick="window.print()">Print</button>
      <h1>Day schedule — ${new Date(selectedDate + 'T12:00:00').toLocaleDateString()}</h1>
      <table><thead><tr><th>Time</th><th>Patient</th><th>MRD</th><th>Phone</th><th>Duration</th><th>Notes</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6">No appointments</td></tr>'}</tbody></table>
      </body></html>`);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Schedule</h2>
          <p className="page-subtitle">Calendar, day agenda, and WhatsApp appointment reminders</p>
        </div>
        <div className="d-flex gap-2">
          <button type="button" className="btn btn-outline-primary" onClick={printDay}>
            <i className="fas fa-print me-1"></i>Print day
          </button>
          <Link to="/reminders" className="btn btn-outline-success"><i className="fab fa-whatsapp me-1"></i>Reminders</Link>
        </div>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="row">
        <div className="col-lg-4 mb-4">
          <div className="card p-3">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <button className="btn btn-sm btn-outline-secondary" onClick={prevMonth}>&laquo;</button>
              <h5 className="mb-0">{MONTHS[viewMonth - 1]} {viewYear}</h5>
              <button className="btn btn-sm btn-outline-secondary" onClick={nextMonth}>&raquo;</button>
            </div>
            <div className="schedule-cal text-center small fw-semibold text-muted mb-1">
              {WEEKDAYS.map(w => <div key={w}>{w}</div>)}
            </div>
            <div className="schedule-cal">
              {calendarCells.map(cell => {
                if (!cell.date) return <div className="schedule-pad" key={cell.key} />;
                const iso = `${cell.date.getFullYear()}-${String(cell.date.getMonth() + 1).padStart(2, '0')}-${String(cell.date.getDate()).padStart(2, '0')}`;
                const count = dayCounts[iso] || 0;
                const isSelected = selectedDate === iso;
                const isToday = sameDay(cell.date, today);
                return (
                  <button
                    type="button"
                    key={cell.key}
                    className={`${isSelected ? 'is-selected' : ''} ${isToday ? 'is-today' : ''}`}
                    onClick={() => {
                      setSelectedDate(iso);
                      setForm(f => ({ ...f, scheduled_at: `${iso}T10:00` }));
                    }}
                  >
                    <span>{cell.date.getDate()}</span>
                    {count > 0 ? <span className="day-count">{count}</span> : <span className="day-count" style={{ visibility: 'hidden' }}>0</span>}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="col-lg-8 mb-4">
          <div className="card mb-3">
            <div className="card-header d-flex justify-content-between align-items-center">
              <h5 className="mb-0">
                Day agenda — {new Date(selectedDate + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}
              </h5>
              <span className="badge badge-soft">{openDay.length} open</span>
            </div>
            {dayAppts.length === 0 ? (
              <div className="p-4 text-muted text-center">No appointments on this day</div>
            ) : (
              <div>
                {[...openDay, ...cancelledDay].map(a => {
                  const chip = a.status === 'arrived' ? 'waiting' : a.status === 'in_consult' ? 'consult' : a.status === 'completed' ? 'done' : a.status === 'cancelled' ? 'cancelled' : '';
                  const label = a.registration_status === 'cancelled'
                    ? 'Registration cancelled'
                    : a.status === 'arrived' ? 'Waiting' : a.status === 'in_consult' ? 'In consult' : a.status === 'completed' ? 'Done' : a.status === 'cancelled' ? 'Appointment cancelled' : 'Booked';
                  return (
                    <div key={a.id} className={`schedule-slot ${a.status === 'cancelled' ? 'is-cancelled' : ''}`}>
                      <div>
                        <div className="schedule-time">{new Date(a.scheduled_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</div>
                        <div className="small text-muted">{a.duration_minutes} min</div>
                      </div>
                      <div>
                        <div className="d-flex justify-content-between gap-2 flex-wrap">
                          <div>
                            <div className="fw-semibold">
                              {a.patient_name}
                              {a.token_number ? <span className="schedule-chip ms-2">Token {a.token_number}</span> : null}
                            </div>
                            <div className="small text-muted">
                              {a.patient_contact || 'No phone'}
                              {' · '}
                              {(a.patient_mrd || '').startsWith('TMP-') ? `Temp ${a.patient_mrd}` : (a.patient_mrd || 'No MRD')}
                              {a.notes ? ` · ${a.notes}` : ''}
                            </div>
                          </div>
                          <span className={`schedule-chip ${chip}`}>{label}</span>
                        </div>
                        {a.status !== 'cancelled' && !isRegistration && (a.status === 'arrived' || a.status === 'in_consult') && (
                          <div className="d-flex gap-1 mt-2 flex-wrap">
                            <input className="form-control form-control-sm" style={{ width: 88 }} placeholder="BP" defaultValue={a.bp_systolic && a.bp_diastolic ? `${a.bp_systolic}/${a.bp_diastolic}` : ''} id={`bp-${a.id}`} />
                            <input className="form-control form-control-sm" style={{ width: 76 }} placeholder="Pulse" defaultValue={a.pulse ?? ''} id={`pulse-${a.id}`} />
                            <input className="form-control form-control-sm" style={{ width: 72 }} placeholder="Wt" defaultValue={a.weight ?? ''} id={`wt-${a.id}`} />
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => saveVitals(a)}>Save</button>
                          </div>
                        )}
                        {a.status !== 'cancelled' && (
                          <div className="schedule-actions">
                            {a.status === 'scheduled' && (
                              <button className="btn btn-sm btn-outline-success" disabled={busyId === a.id || !a.patient_contact} onClick={() => remind(a, false)}>
                                <i className="fab fa-whatsapp me-1"></i>Remind
                              </button>
                            )}
                            {a.status === 'scheduled' && autoSend && (
                              <button className="btn btn-sm btn-success" disabled={busyId === a.id} onClick={() => remind(a, true)}>Send</button>
                            )}
                            {a.status === 'scheduled' && !isRegistration && (
                              <button className="btn btn-sm btn-success" onClick={() => api.updateAppointmentStatus(a.id, 'arrived').then(load)}>Arrive</button>
                            )}
                            {!isRegistration && a.status === 'arrived' && (
                              <button className="btn btn-sm btn-primary" onClick={() => api.updateAppointmentStatus(a.id, 'in_consult').then(load)}>In consult</button>
                            )}
                            {!isRegistration && (a.status === 'arrived' || a.status === 'in_consult') && (
                              <>
                                <button className="btn btn-sm btn-outline-success" onClick={() => api.updateAppointmentStatus(a.id, 'completed').then(load)}>Done</button>
                                <button className="btn btn-sm btn-outline-dark" onClick={() => printToken(a)}>Token</button>
                                <Link to={`/patients/${a.patient_id}/visits/new`} className="btn btn-sm btn-primary">Start visit</Link>
                              </>
                            )}
                            {(a.status === 'scheduled' || !isRegistration) && (
                              <button className="btn btn-sm btn-outline-danger" onClick={() => api.updateAppointmentStatus(a.id, 'cancelled').then(load)}>Cancel</button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="row g-3">
            <div className="col-md-6">
              <div className="card p-3 h-100">
                <h5 className="mb-3">Schedule appointment</h5>
                <form onSubmit={create}>
                  <PatientSearch
                    patients={patients}
                    patientId={form.patient_id}
                    query={patientQuery}
                    open={patientOpen}
                    onQuery={value => { setPatientQuery(value); setPatientOpen(true); setForm({ ...form, patient_id: '' }); }}
                    onOpen={setPatientOpen}
                    onPick={id => { setForm({ ...form, patient_id: id }); setPatientQuery(''); setPatientOpen(false); }}
                  />
                  {!form.patient_id && patientQuery.trim() && (
                    <div className="border rounded p-2 mb-2">
                      <div className="small text-muted mb-2">Booked before registration. They keep a temporary id until the desk registers them.</div>
                      <div className="row g-2">
                        <div className="col-6">
                          <input className="form-control" placeholder="Mobile" value={form.contact} onChange={e => setForm({ ...form, contact: e.target.value })} />
                        </div>
                        <div className="col-3">
                          <input className="form-control" placeholder="Age" value={form.age} onChange={e => setForm({ ...form, age: e.target.value })} />
                        </div>
                        <div className="col-3">
                          <select className="form-select" value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })}>
                            <option>Other</option>
                            <option>Male</option>
                            <option>Female</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  )}
                  <label className="form-label small mb-1">Date and time</label>
                  <input type="datetime-local" className="form-control mb-2" required value={form.scheduled_at || toLocalInputValue(new Date(`${selectedDate}T10:00:00`))}
                    onChange={e => setForm({ ...form, scheduled_at: e.target.value })} />
                  <div className="row g-2 mb-2">
                    <div className="col-6">
                      <label className="form-label small mb-1">Minutes</label>
                      <input type="number" className="form-control" value={form.duration_minutes} onChange={e => setForm({ ...form, duration_minutes: e.target.value })} />
                    </div>
                    <div className="col-6">
                      <label className="form-label small mb-1">Source</label>
                      <select className="form-select" value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}>
                        <option value="in_clinic">In clinic</option>
                        <option value="online">Online</option>
                        <option value="walk_in">Walk-in</option>
                      </select>
                    </div>
                  </div>
                  <label className="form-label small mb-1">Notes</label>
                  <textarea className="form-control mb-3" placeholder="Optional" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
                  <button className="btn btn-primary w-100">Schedule</button>
                </form>
              </div>
            </div>
            <div className="col-md-6">
              <div className="card h-100">
                <div className="card-header"><h5 className="mb-0">Upcoming ({upcoming.length})</h5></div>
                <div className="list-group list-group-flush" style={{ maxHeight: 280, overflow: 'auto' }}>
                  {upcoming.slice(0, 12).map(a => (
                    <div key={a.id} className="list-group-item d-flex justify-content-between gap-2 align-items-start">
                      <button type="button" className="btn btn-link text-start p-0 text-decoration-none"
                        onClick={() => setSelectedDate(a.scheduled_at.slice(0, 10))}>
                        <div className="fw-semibold">{a.patient_name}</div>
                        <div className="small text-muted">{new Date(a.scheduled_at).toLocaleString()}</div>
                        {(a.patient_mrd || '').startsWith('TMP-') && <div className="small text-muted">Temp {a.patient_mrd}</div>}
                      </button>
                      <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => api.updateAppointmentStatus(a.id, 'cancelled').then(load)}>Cancel</button>
                    </div>
                  ))}
                  {upcoming.length === 0 && <div className="p-3 text-muted">No upcoming appointments</div>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
