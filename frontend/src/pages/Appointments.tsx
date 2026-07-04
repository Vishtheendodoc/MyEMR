import { useEffect, useMemo, useState } from 'react';
import { api, Appointment, Patient } from '../api/client';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export default function Appointments() {
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dayCounts, setDayCounts] = useState<Record<string, number>>({});
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [form, setForm] = useState({ patient_id: '', scheduled_at: '', duration_minutes: '15', notes: '' });

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

  const filteredAppts = selectedDate
    ? appts.filter(a => a.scheduled_at.startsWith(selectedDate))
    : appts;

  const prevMonth = () => {
    if (viewMonth === 1) { setViewYear(y => y - 1); setViewMonth(12); }
    else setViewMonth(m => m - 1);
    setSelectedDate(null);
  };

  const nextMonth = () => {
    if (viewMonth === 12) { setViewYear(y => y + 1); setViewMonth(1); }
    else setViewMonth(m => m + 1);
    setSelectedDate(null);
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.createAppointment({
      patient_id: Number(form.patient_id),
      scheduled_at: new Date(form.scheduled_at).toISOString(),
      duration_minutes: Number(form.duration_minutes),
      notes: form.notes || null,
    });
    setForm({ patient_id: '', scheduled_at: '', duration_minutes: '15', notes: '' });
    load();
  };

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-calendar-alt me-2"></i>Appointments</h2>
      <div className="row">
        <div className="col-lg-5 mb-4">
          <div className="card p-3">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <button className="btn btn-sm btn-outline-secondary" onClick={prevMonth}>&laquo;</button>
              <h5 className="mb-0">{MONTHS[viewMonth - 1]} {viewYear}</h5>
              <button className="btn btn-sm btn-outline-secondary" onClick={nextMonth}>&raquo;</button>
            </div>
            <div className="row g-1 text-center small fw-semibold text-muted mb-1">
              {WEEKDAYS.map(w => <div className="col" key={w}>{w}</div>)}
            </div>
            <div className="row g-1">
              {calendarCells.map(cell => {
                if (!cell.date) return <div className="col" key={cell.key} style={{ minHeight: 52 }} />;
                const iso = cell.date.toISOString().slice(0, 10);
                const count = dayCounts[iso] || 0;
                const isSelected = selectedDate === iso;
                const isToday = sameDay(cell.date, today);
                return (
                  <div className="col" key={cell.key}>
                    <button
                      type="button"
                      className={`btn w-100 p-1 ${isSelected ? 'btn-primary' : 'btn-light border'} ${isToday && !isSelected ? 'border-primary' : ''}`}
                      style={{ minHeight: 52 }}
                      onClick={() => setSelectedDate(isSelected ? null : iso)}
                    >
                      <div>{cell.date.getDate()}</div>
                      {count > 0 && (
                        <span className={`badge ${isSelected ? 'bg-light text-primary' : 'bg-primary'}`}>{count}</span>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
            {selectedDate && (
              <div className="mt-2 text-center">
                <button className="btn btn-sm btn-link" onClick={() => setSelectedDate(null)}>Show all appointments</button>
              </div>
            )}
          </div>
        </div>

        <div className="col-lg-7 mb-4">
          <div className="card mb-3">
            <div className="card-header d-flex justify-content-between">
              <h5 className="mb-0">
                {selectedDate
                  ? `Appointments — ${new Date(selectedDate + 'T12:00:00').toLocaleDateString()}`
                  : 'All Upcoming Appointments'}
              </h5>
              <span className="badge bg-secondary">{filteredAppts.length}</span>
            </div>
            <div className="table-responsive">
              <table className="table mb-0">
                <thead><tr><th>Date/Time</th><th>Patient</th><th>Duration</th><th>Notes</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {filteredAppts.length === 0 ? (
                    <tr><td colSpan={6} className="text-center text-muted py-4">No appointments</td></tr>
                  ) : filteredAppts.map(a => (
                    <tr key={a.id}>
                      <td>{new Date(a.scheduled_at).toLocaleString()}</td>
                      <td>{a.patient_name}</td>
                      <td>{a.duration_minutes} min</td>
                      <td className="small text-muted">{a.notes || '-'}</td>
                      <td><span className={`badge bg-${a.status === 'completed' ? 'success' : a.status === 'cancelled' ? 'secondary' : 'primary'}`}>{a.status}</span></td>
                      <td>
                        {a.status === 'scheduled' && (
                          <>
                            <button className="btn btn-sm btn-success me-1" onClick={() => api.updateAppointmentStatus(a.id, 'completed').then(load)}>Done</button>
                            <button className="btn btn-sm btn-outline-secondary" onClick={() => api.updateAppointmentStatus(a.id, 'cancelled').then(load)}>Cancel</button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card p-3">
            <h5>Schedule Appointment</h5>
            <form onSubmit={create}>
              <select className="form-select mb-2" required value={form.patient_id} onChange={e => setForm({ ...form, patient_id: e.target.value })}>
                <option value="">Select patient</option>
                {patients.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input type="datetime-local" className="form-control mb-2" required value={form.scheduled_at} onChange={e => setForm({ ...form, scheduled_at: e.target.value })} />
              <input type="number" className="form-control mb-2" placeholder="Duration (min)" value={form.duration_minutes} onChange={e => setForm({ ...form, duration_minutes: e.target.value })} />
              <textarea className="form-control mb-2" placeholder="Notes" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
              <button className="btn btn-primary w-100">Schedule</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
