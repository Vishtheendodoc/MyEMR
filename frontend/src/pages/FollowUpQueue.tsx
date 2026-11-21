import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, FollowUpItem } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { openPrintHtml } from '../utils/openPrintHtml';

type Bucket = 'all' | 'overdue' | 'today' | 'upcoming' | 'cancelled' | 'done';

export default function FollowUpQueue() {
  const { user } = useAuth();
  const showDiagnosis = user?.role === 'doctor' || user?.role === 'admin';
  const [items, setItems] = useState<FollowUpItem[]>([]);
  const [bucket, setBucket] = useState<Bucket>('all');
  const [error, setError] = useState('');
  const [rescheduleId, setRescheduleId] = useState<number | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [rescheduleTime, setRescheduleTime] = useState('10:00');
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = () => {
    api.followUps('all', 60)
      .then(setItems)
      .catch(e => setError(e.message));
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    if (bucket === 'all') return items;
    return items.filter(i => (i.bucket || (i.days_overdue > 0 ? 'overdue' : i.days_until === 0 ? 'today' : 'upcoming')) === bucket);
  }, [items, bucket]);

  const bucketOf = (i: FollowUpItem) =>
    i.bucket || (i.days_overdue > 0 ? 'overdue' : (i.days_until ?? 0) === 0 ? 'today' : 'upcoming');

  const counts = useMemo(() => ({
    all: items.length,
    overdue: items.filter(i => bucketOf(i) === 'overdue').length,
    today: items.filter(i => bucketOf(i) === 'today').length,
    upcoming: items.filter(i => bucketOf(i) === 'upcoming').length,
    cancelled: items.filter(i => bucketOf(i) === 'cancelled').length,
    done: items.filter(i => bucketOf(i) === 'done').length,
  }), [items]);

  const todayList = useMemo(
    () => items.filter(i => bucketOf(i) === 'today'),
    [items],
  );

  const printToday = () => {
    const rows = todayList.map(i => `
      <tr>
        <td>${i.patient_name}</td>
        <td>${i.patient_mrd || '—'}</td>
        <td>${i.patient_contact || '—'}</td>
        ${showDiagnosis ? `<td>${i.diagnosis || '—'}</td>` : ''}
        <td>${i.follow_up_notes || '—'}</td>
      </tr>`).join('');
    openPrintHtml(`<!doctype html><html><head><meta charset="utf-8"><title>Today's Follow-up Queue</title>
      <style>
        body{font-family:Segoe UI,Arial,sans-serif;padding:24px;color:#14212b}
        h1{font-size:22px;margin:0 0 4px}
        p{color:#5b6b78;margin:0 0 16px}
        table{width:100%;border-collapse:collapse}
        th,td{border:1px solid #d7e0e7;padding:8px 10px;text-align:left;font-size:13px}
        th{background:#f3f7f8}
        @media print{button{display:none}}
      </style></head><body>
      <button onclick="window.print()">Print</button>
      <h1>Today's Follow-up Queue</h1>
      <p>${new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })} · ${todayList.length} patient(s)</p>
      <table><thead><tr><th>Patient</th><th>MRD</th><th>Phone</th>${showDiagnosis ? '<th>Diagnosis</th>' : ''}<th>Notes</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5">No follow-ups due today</td></tr>'}</tbody></table>
      </body></html>`);
  };

  const saveReschedule = async () => {
    if (!rescheduleId || !rescheduleDate) return;
    setBusyId(rescheduleId);
    try {
      await api.rescheduleFollowUp(rescheduleId, rescheduleDate, undefined, rescheduleTime || '10:00');
      setRescheduleId(null);
      setRescheduleDate('');
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reschedule failed');
    } finally {
      setBusyId(null);
    }
  };

  const minDate = new Date().toISOString().slice(0, 10);

  return (
    <div>
      <div className="page-header no-print">
        <div>
          <h2>Follow-ups</h2>
          <p className="page-subtitle">Due visits. Revisit, scheduling, and WhatsApp reminders are on the Reminders page.</p>
        </div>
        <div className="d-flex gap-2 flex-wrap">
          <button type="button" className="btn btn-outline-primary" onClick={printToday}>
            <i className="fas fa-print me-1"></i>Print today ({todayList.length})
          </button>
          <Link to="/reminders" className="btn btn-primary">
            <i className="fab fa-whatsapp me-1"></i>Reminders
          </Link>
        </div>
      </div>

      {error && <div className="alert alert-danger no-print">{error}</div>}

      <div className="filter-bar mb-3 no-print">
        {([
          { id: 'all' as const, label: 'All' },
          { id: 'overdue' as const, label: 'Overdue' },
          { id: 'today' as const, label: 'Today' },
          { id: 'upcoming' as const, label: 'Upcoming' },
          { id: 'cancelled' as const, label: 'Cancelled' },
          { id: 'done' as const, label: 'Done' },
        ]).map(t => (
          <button
            key={t.id}
            type="button"
            className={`btn btn-sm ${bucket === t.id ? 'btn-primary' : 'btn-outline-secondary'}`}
            onClick={() => setBucket(t.id)}
          >
            {t.label} <span className="badge badge-soft ms-1">{counts[t.id]}</span>
          </button>
        ))}
      </div>

      <div className="card">
        <div className="table-responsive">
          <table className="table mb-0 align-middle">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Due</th>
                <th>Status</th>
                {showDiagnosis && <th>Diagnosis</th>}
                <th className="no-print">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={showDiagnosis ? 5 : 4} className="text-center text-muted py-4">No follow-ups in this bucket</td></tr>
              ) : filtered.map(item => {
                const b = bucketOf(item);
                return (
                  <tr key={item.visit_id} className={b === 'cancelled' || b === 'done' ? 'text-muted' : undefined}>
                    <td>
                      <div className="fw-semibold">{item.patient_name}</div>
                      <div className="small text-muted">
                        {item.patient_mrd || 'No MRD'}
                        {item.patient_contact ? ` · ${item.patient_contact}` : ' · no phone'}
                      </div>
                      {!showDiagnosis && item.follow_up_notes && <div className="small text-muted">{item.follow_up_notes}</div>}
                    </td>
                    <td>{new Date(`${item.follow_up_date.slice(0, 10)}T12:00:00`).toLocaleDateString()}</td>
                    <td>
                      {b === 'cancelled' && <span className="badge bg-secondary">Cancelled</span>}
                      {b === 'done' && <span className="badge bg-success">Done</span>}
                      {b === 'overdue' && <span className="badge bg-danger">{item.days_overdue}d overdue</span>}
                      {b === 'today' && <span className="badge bg-warning text-dark">Due today</span>}
                      {b === 'upcoming' && <span className="badge badge-soft">In {item.days_until}d</span>}
                    </td>
                    {showDiagnosis && (
                      <td>
                        <div>{item.diagnosis || '—'}</div>
                        {item.follow_up_notes && <div className="small text-muted">{item.follow_up_notes}</div>}
                      </td>
                    )}
                    <td className="no-print">
                      <div className="d-flex flex-wrap gap-1">
                        <button type="button" className="btn btn-sm btn-outline-primary" disabled={busyId === item.visit_id}
                          onClick={() => {
                            setRescheduleId(item.visit_id);
                            setRescheduleDate(item.follow_up_date.slice(0, 10));
                            setRescheduleTime('10:00');
                          }}>Reschedule</button>
                        <Link to={`/patients/${item.patient_id}`} className="btn btn-sm btn-link">Chart</Link>
                      </div>
                      {rescheduleId === item.visit_id && (
                        <div className="d-flex gap-1 mt-2 flex-wrap">
                          <input type="date" className="form-control form-control-sm" style={{ width: 150 }} min={minDate} value={rescheduleDate}
                            onChange={e => setRescheduleDate(e.target.value)} />
                          <input type="time" className="form-control form-control-sm" style={{ width: 120 }} value={rescheduleTime}
                            onChange={e => setRescheduleTime(e.target.value)} />
                          <button type="button" className="btn btn-sm btn-primary" disabled={!rescheduleDate || busyId === item.visit_id} onClick={saveReschedule}>Save</button>
                          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setRescheduleId(null)}>Cancel</button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
