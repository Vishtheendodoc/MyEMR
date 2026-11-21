import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ReminderQueueItem } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { formatClinicDate, formatClinicDateTime } from '../utils/clinicTime';

export default function Reminders() {
  const { user } = useAuth();
  const canEditNames = user?.role === 'doctor' || user?.role === 'admin';
  const [items, setItems] = useState<ReminderQueueItem[]>([]);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof api.reminderHistory>>>([]);
  const [days, setDays] = useState(3);
  const [autoSendAvailable, setAutoSendAvailable] = useState(false);
  const [clinicName, setClinicName] = useState('');
  const [doctorName, setDoctorName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState('');
  const [rule, setRule] = useState('1 day before appointment; Monday appointments reminded on Friday');
  const [runningAuto, setRunningAuto] = useState(false);

  const load = () => {
    api.remindersQueue(days).then(setItems).catch(e => setError(e.message));
    api.reminderHistory(30).then(setHistory).catch(() => {});
  };

  useEffect(() => {
    api.remindersStatus().then(s => {
      setAutoSendAvailable(s.auto_send_available);
      setClinicName(s.clinic_name || '');
      setDoctorName(s.doctor_name || '');
      if (s.rule) setRule(s.rule);
    }).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [days]);

  const runAuto = async () => {
    setRunningAuto(true);
    setError('');
    setMsg('');
    try {
      const res = await api.remindersAutoRun();
      setMsg(`Auto-run complete: ${res.sent} sent, ${res.queued} queued, ${res.skipped} skipped, ${res.failed} failed.`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Auto-run failed');
    } finally {
      setRunningAuto(false);
    }
  };

  const sendOne = async (item: ReminderQueueItem, auto: boolean) => {
    setBusy(item.id);
    setError('');
    setMsg('');
    try {
      const res = await api.sendReminder({
        source_type: item.source_type,
        source_id: item.source_id,
        auto_send: auto,
        message: item.message,
      });
      if (!auto && res.whatsapp_url) {
        window.open(res.whatsapp_url, '_blank', 'noopener,noreferrer');
        setMsg(`Opened WhatsApp for ${item.patient_name}`);
      } else if (auto && res.status === 'sent') {
        setMsg(`Auto-sent to ${item.patient_name}`);
      } else if (auto && res.status === 'failed') {
        setError(res.error || 'Auto-send failed — try WhatsApp link instead');
        if (res.whatsapp_url) window.open(res.whatsapp_url, '_blank', 'noopener,noreferrer');
      }
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send reminder');
    } finally {
      setBusy(null);
    }
  };

  const saveNames = async () => {
    setError('');
    setMsg('');
    try {
      const saved = await api.saveReminderNames({ clinic_name: clinicName.trim(), doctor_name: doctorName.trim() });
      setClinicName(saved.clinic_name);
      setDoctorName(saved.doctor_name);
      setMsg('Reminder names saved.');
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the names');
    }
  };

  const scheduleOne = async (item: ReminderQueueItem) => {
    const day = item.due_at.slice(0, 10);
    setBusy(item.id);
    setError('');
    setMsg('');
    try {
      await api.rescheduleFollowUp(item.source_id, day, undefined, '10:00');
      setMsg(`${item.patient_name} is on the calendar at 10:00.`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not schedule');
    } finally {
      setBusy(null);
    }
  };

  const cancelOne = async (item: ReminderQueueItem) => {
    if (!window.confirm(`Cancel the reminder for ${item.patient_name}? It will not be sent.`)) return;
    setBusy(item.id);
    setError('');
    setMsg('');
    try {
      await api.cancelReminder({ source_type: item.source_type, source_id: item.source_id });
      setMsg(`Cancelled the reminder for ${item.patient_name}.`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not cancel this reminder');
    } finally {
      setBusy(null);
    }
  };

  const sendAllLinks = async () => {
    const pending = items.filter(i => i.whatsapp_url && !i.already_reminded);
    if (!pending.length) {
      setMsg('Nothing pending with a phone number.');
      return;
    }
    if (!confirm(`Open WhatsApp for ${pending.length} patient(s)? Your browser may block multiple pop-ups — allow them for this site.`)) return;
    for (const item of pending) {
      await sendOne(item, false);
      await new Promise(r => setTimeout(r, 400));
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Reminders</h2>
          <p className="page-subtitle">
            {rule} · {clinicName}
            {autoSendAvailable ? ' · Twilio auto-send enabled' : ' · click-to-chat (wa.me)'}
          </p>
        </div>
        <div className="d-flex gap-2 flex-wrap align-items-center">
          <select className="form-select form-select-sm" style={{ width: 140 }} value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value={1}>Next 1 day</option>
            <option value={2}>Next 2 days</option>
            <option value={3}>Next 3 days</option>
            <option value={7}>Next 7 days</option>
          </select>
          <button type="button" className="btn btn-primary" disabled={runningAuto} onClick={runAuto}>
            {runningAuto ? 'Running…' : 'Run due reminders'}
          </button>
          <button type="button" className="btn btn-outline-success" onClick={sendAllLinks}>
            <i className="fab fa-whatsapp me-1"></i>Remind all pending
          </button>
          <Link to="/follow-ups" className="btn btn-outline-secondary">Follow-ups</Link>
        </div>
      </div>

      <div className="alert alert-info">
        <strong>Auto rule:</strong> reminders go out 1 day before the appointment. If the visit is on Monday, the reminder is sent on Friday.
        The server also runs this hourly. {!autoSendAvailable && (
          <> Without Twilio, due items are queued for WhatsApp click-to-chat — configure <code>TWILIO_*</code> in backend <code>.env</code> for hands-free send.</>
        )}
      </div>

      <div className="card p-3 mb-4">
        <h5 className="mb-1">Names in the message</h5>
        <p className="text-muted small">These replace Demo Clinic and the sample doctor name in appointment and follow-up reminders.</p>
        <div className="row g-2 align-items-end">
          <div className="col-md-4">
            <label className="form-label small mb-1">Clinic name</label>
            <input className="form-control" value={clinicName} disabled={!canEditNames} onChange={e => setClinicName(e.target.value)} />
          </div>
          <div className="col-md-4">
            <label className="form-label small mb-1">Doctor name</label>
            <input className="form-control" value={doctorName} disabled={!canEditNames} onChange={e => setDoctorName(e.target.value)} />
          </div>
          {canEditNames && (
            <div className="col-md-4">
              <button type="button" className="btn btn-primary" onClick={saveNames}>Save names</button>
            </div>
          )}
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {msg && <div className="alert alert-success">{msg}</div>}

      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between">
          <h5 className="mb-0">Due soon</h5>
          <span className="badge badge-soft">{items.length}</span>
        </div>
        <div className="table-responsive">
          <table className="table mb-0 align-middle">
            <thead>
              <tr>
                <th>When</th><th>Patient</th><th>Type</th><th>Preview</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={6} className="text-center text-muted py-4">No reminders in this window</td></tr>
              ) : items.map(item => (
                <tr key={item.id} className={item.auto_due_today && !item.already_reminded ? 'table-warning' : undefined}>
                  <td>
                    <div>{/^\d{4}-\d{2}-\d{2}$/.test(item.due_at) ? formatClinicDate(item.due_at) : new Date(item.due_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true })}</div>
                    {item.remind_on && (
                      <div className="small text-muted">Remind on {formatClinicDate(item.remind_on)}</div>
                    )}
                  </td>
                  <td>
                    <div className="fw-semibold">{item.patient_name}</div>
                    <div className="small text-muted">{item.patient_contact || 'No phone'}</div>
                  </td>
                  <td>
                    <span className="badge badge-soft">{item.label}</span>
                    {item.auto_due_today && !item.already_reminded && (
                      <div className="small text-warning-emphasis mt-1">Due today</div>
                    )}
                    {item.due_at.slice(0, 10) < new Date().toLocaleDateString('en-CA') && (
                      <div className="small text-danger mt-1">Overdue</div>
                    )}
                  </td>
                  <td className="small" style={{ maxWidth: 280 }}>{item.message.slice(0, 120)}…</td>
                  <td>
                    {item.already_reminded
                      ? <span className="badge bg-success">Reminded</span>
                      : item.auto_due_today
                        ? <span className="badge bg-danger">Auto due</span>
                        : <span className="badge bg-warning text-dark">Pending</span>}
                  </td>
                  <td className="text-end">
                    <div className="d-flex flex-wrap gap-1 justify-content-end">
                    <Link to={`/patients/${item.patient_id}/visits/new`} className="btn btn-sm btn-primary">Revisit</Link>
                    {item.source_type === 'follow_up' && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-secondary"
                        disabled={busy === item.id}
                        onClick={() => scheduleOne(item)}
                      >
                        Schedule
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-success"
                      disabled={busy === item.id || !item.whatsapp_url}
                      onClick={() => sendOne(item, false)}
                    >
                      <i className="fab fa-whatsapp me-1"></i>WhatsApp
                    </button>
                    {autoSendAvailable && (
                      <button
                        type="button"
                        className="btn btn-sm btn-success me-1"
                        disabled={busy === item.id || !item.patient_contact}
                        onClick={() => sendOne(item, true)}
                      >
                        Auto-send
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-danger"
                      disabled={busy === item.id}
                      onClick={() => cancelOne(item)}
                    >
                      Cancel
                    </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h5 className="mb-0">Recent reminder log</h5></div>
        <div className="table-responsive">
          <table className="table mb-0">
            <thead>
              <tr><th>When</th><th>Patient</th><th>Channel</th><th>Status</th><th>Error</th></tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-muted py-3">No reminders sent yet</td></tr>
              ) : history.map(h => (
                <tr key={h.id}>
                  <td>{formatClinicDateTime(h.sent_at || h.created_at)}</td>
                  <td>{h.patient_name}</td>
                  <td>{h.channel}</td>
                  <td><span className={`badge bg-${h.status === 'sent' || h.status === 'opened' ? 'success' : h.status === 'failed' ? 'danger' : 'secondary'}`}>{h.status}</span></td>
                  <td className="small text-muted">{h.error || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
