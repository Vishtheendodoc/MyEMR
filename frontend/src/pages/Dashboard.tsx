import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, DashboardData, TodayConsult } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { formatClinicClock, formatClinicDate } from '../utils/clinicTime';

const FILTERS = [
  ['all', 'All'],
  ['waiting', 'Waiting'],
  ['in_consult', 'In consult'],
  ['done', 'Done'],
  ['new', 'New'],
  ['revisit', 'Revisit'],
  ['walk_in', 'Walk-in'],
  ['online', 'Online'],
] as const;

type FilterId = (typeof FILTERS)[number][0];

function greeting() {
  const hour = Number(new Intl.DateTimeFormat('en-GB', {
    hour: 'numeric',
    hourCycle: 'h23',
    timeZone: 'Asia/Kolkata',
  }).format(new Date()));
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function queueClock(value?: string | null) {
  if (!value) return '—';
  const raw = value.trim();
  if (!/Z$/i.test(raw) && !/[+-]\d{2}:\d{2}$/.test(raw)) {
    const match = raw.match(/(\d{2}):(\d{2})/);
    if (match) {
      const hour = Number(match[1]);
      const suffix = hour >= 12 ? 'pm' : 'am';
      return `${hour % 12 || 12}:${match[2]} ${suffix}`;
    }
  }
  return formatClinicClock(raw);
}

function statusLabel(status: string) {
  if (status === 'scheduled') return 'Booked';
  if (status === 'arrived') return 'Waiting';
  if (status === 'in_consult') return 'In consult';
  if (status === 'completed') return 'Done';
  if (status === 'no_show') return 'No show';
  if (status === 'due') return 'Follow-up due';
  if (status === 'registration_cancelled') return 'Registration cancelled';
  if (status === 'appointment_cancelled') return 'Appointment cancelled';
  if (status === 'cancelled') return 'Cancelled';
  return status;
}

function isClosed(status: string) {
  return status === 'cancelled' || status === 'registration_cancelled' || status === 'appointment_cancelled';
}

function matches(row: TodayConsult, filter: FilterId) {
  if (filter === 'all') return true;
  if (isClosed(row.status)) return false;
  if (filter === 'waiting') return row.status === 'scheduled' || row.status === 'arrived' || row.status === 'due';
  if (filter === 'in_consult') return row.status === 'in_consult';
  if (filter === 'done') return row.status === 'completed';
  if (filter === 'new' || filter === 'revisit') return row.kind === filter;
  return row.channel === filter;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<FilterId>('all');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [overdue, setOverdue] = useState<number | null>(null);

  const load = () => {
    api.dashboard().then(setData).catch(e => setError(e.message));
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    api.followUps('overdue').then(rows => setOverdue(rows.length)).catch(() => setOverdue(null));
  }, []);

  const today = data?.today;
  const rows = useMemo(
    () => (today?.consultations || []).filter(row => matches(row, filter)),
    [today, filter],
  );

  const markArrived = async (row: TodayConsult) => {
    const key = row.appointment_id ? `a-${row.appointment_id}` : `p-${row.patient_id}`;
    setBusyId(key);
    try {
      if (row.appointment_id) await api.updateAppointmentStatus(row.appointment_id, 'arrived');
      else await api.checkInQueue({ patient_id: row.patient_id, channel: row.channel || 'walk_in', kind: row.kind || 'new' });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update the queue');
    } finally {
      setBusyId(null);
    }
  };

  if (error && !data) return <div className="alert alert-danger">{error}</div>;
  if (!data || !today) return <div className="text-center py-5 text-muted">Loading today’s clinic…</div>;

  const counts: Record<FilterId, number> = {
    all: today.consultations.length,
    waiting: today.booked + today.waiting,
    in_consult: today.in_consult,
    done: today.done,
    new: today.new,
    revisit: today.revisit,
    walk_in: today.walk_in,
    online: today.online,
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{greeting()}{user?.doctor_name ? `, Dr. ${user.doctor_name}` : ''}</h2>
          <p className="page-subtitle">Today’s consultations — {formatClinicDate(today.date)}</p>
        </div>
        <div className="d-flex gap-2">
          <Link to="/appointments" className="btn btn-outline-primary">Schedule</Link>
          <Link to="/patients/new" className="btn btn-primary">
            <i className="fas fa-user-plus me-1"></i>Add patient
          </Link>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {overdue !== null && (
        <div className="task-row mb-3">
          <Link to="/follow-ups" className="task-chip">Overdue follow-ups · {overdue}</Link>
          <Link to="/patients" className="task-chip">Open a chart for results and screening</Link>
        </div>
      )}

      <div className="consult-filters mb-3">
        {FILTERS.map(([id, label]) => (
          <button key={id} type="button" className={filter === id ? 'active' : ''} onClick={() => setFilter(id)}>
            {label} · {counts[id]}
          </button>
        ))}
      </div>

      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Consultation list</h5>
          <span className="small text-muted">{rows.length} shown</span>
        </div>
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead>
              <tr>
                <th>Time</th>
                <th>Token</th>
                <th>Patient</th>
                <th>Visit</th>
                <th>Source</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center text-muted py-4">
                    Nothing in this list today. Register a patient, or book from Schedule.
                  </td>
                </tr>
              ) : rows.map(row => (
                <tr key={`${row.appointment_id || 'v'}-${row.visit_id || row.patient_id}`} className={isClosed(row.status) ? 'text-muted' : undefined}>
                  <td className="fw-semibold">{queueClock(row.scheduled_at)}</td>
                  <td>{row.token_number || '—'}</td>
                  <td>
                    <Link to={`/patients/${row.patient_id}`} className="text-decoration-none fw-semibold">
                      {row.patient_name}
                    </Link>
                    <div className="small text-muted">
                      {[row.patient_age, row.patient_sex].filter(Boolean).join(' · ') || '—'}
                      {row.patient_mrd ? ` · ${(row.patient_mrd.startsWith('TMP-')) ? `Temp ${row.patient_mrd}` : row.patient_mrd}` : ''}
                    </div>
                    {row.complaint && <div className="small text-muted text-truncate" style={{ maxWidth: 280 }}>{row.complaint}</div>}
                  </td>
                  <td>
                    <span className={`badge ${row.kind === 'revisit' ? 'queue-revisit' : 'queue-kind'}`}>
                      {row.kind === 'revisit' ? 'Revisit' : 'New'}
                    </span>
                  </td>
                  <td>
                    <span className="badge queue-source">
                      {row.channel === 'walk_in' ? 'Walk-in' : row.channel === 'online' ? 'Online' : 'In clinic'}
                    </span>
                  </td>
                  <td>{statusLabel(row.status)}</td>
                  <td className="text-end text-nowrap">
                    {isClosed(row.status) ? null : !row.appointment_id ? (
                      <button type="button" className="btn btn-sm btn-primary" disabled={busyId === `p-${row.patient_id}`} onClick={() => markArrived(row)}>
                        Token
                      </button>
                    ) : (
                      <>
                        {row.status === 'scheduled' && (
                          <button type="button" className="btn btn-sm btn-outline-secondary me-1" disabled={busyId === `a-${row.appointment_id}`} onClick={() => markArrived(row)}>
                            Arrived
                          </button>
                        )}
                        <Link
                          className="btn btn-sm btn-primary"
                          to={row.visit_id ? `/visits/${row.visit_id}` : `/patients/${row.patient_id}/visits/new`}
                        >
                          {row.visit_id ? 'Open' : 'Start'}
                        </Link>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-md-4">
          <div className="card stat-card">
            <h3>{data.stats.total_patients}</h3>
            <p className="text-muted mb-0">Patients on record</p>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card stat-card">
            <h3>{today.consultations.length}</h3>
            <p className="text-muted mb-0">On today’s list</p>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card stat-card">
            <h3>{today.done}</h3>
            <p className="text-muted mb-0">Consultations finished</p>
          </div>
        </div>
      </div>
    </div>
  );
}
