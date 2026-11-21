import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, Patient, TodayConsult, User } from '../api/client';
import { useAuth } from '../hooks/useAuth';

function sourceLabel(channel: string) {
  if (channel === 'walk_in') return 'Walk-in';
  if (channel === 'online') return 'Online';
  return 'In clinic';
}

function statusLabel(status: string) {
  if (status === 'scheduled') return 'Booked';
  if (status === 'arrived') return 'Waiting';
  if (status === 'in_consult') return 'In consult';
  if (status === 'completed') return 'Done';
  if (status === 'due') return 'Follow-up due';
  if (status === 'registration_cancelled') return 'Registration cancelled';
  if (status === 'appointment_cancelled') return 'Appointment cancelled';
  if (status === 'cancelled') return 'Cancelled';
  return status;
}

export default function Patients() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const isDesk = user?.role === 'registration';
  const showToday = user?.role === 'doctor' || user?.role === 'registration' || user?.role === 'admin';
  const [patients, setPatients] = useState<Patient[]>([]);
  const [queue, setQueue] = useState<TodayConsult[]>([]);
  const [q, setQ] = useState('');
  const [searchType, setSearchType] = useState('name');
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState('revisit');
  const [channel, setChannel] = useState('walk_in');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [doctors, setDoctors] = useState<User[]>([]);
  const [assignTo, setAssignTo] = useState<Record<number, number>>({});

  const load = () => {
    setLoading(true);
    Promise.all([
      api.patients(q || undefined, searchType),
      api.dashboard().catch(() => null),
    ]).then(([rows, board]) => {
      setPatients(rows);
      setQueue(board?.today?.consultations || []);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!isDesk) return;
    api.doctors().then(setDoctors).catch(() => setDoctors([]));
  }, [isDesk]);

  const doctorName = (doctorId?: number | null) => {
    const found = doctors.find(d => d.id === doctorId);
    return found ? `Dr. ${found.doctor_name}` : '';
  };

  const doctorFor = (patient: Patient) => assignTo[patient.id] || patient.doctor_id || '';

  const queuedIds = new Set(queue.map(row => row.patient_id));

  const sendToDoctor = async (patient: Patient) => {
    const doctorId = Number(doctorFor(patient));
    if (!doctorId) {
      setError('Choose the doctor to assign this visit to.');
      return;
    }
    setBusyId(patient.id);
    setError('');
    try {
      await api.setActingDoctor(doctorId);
      await refreshUser();
      const queued = await api.checkInQueue({ patient_id: patient.id, channel, kind, doctor_id: doctorId });
      if (queued.visit_id) navigate(`/billing?visit=${queued.visit_id}`);
      else load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send this patient to the doctor');
    } finally {
      setBusyId(null);
    }
  };

  const cancelAppointment = async (row: TodayConsult) => {
    if (!row.appointment_id) return;
    if (!window.confirm(`Cancel the appointment for ${row.patient_name}? The registration and MRD stay.`)) return;
    setBusyId(row.patient_id);
    setError('');
    try {
      await api.updateAppointmentStatus(row.appointment_id, 'cancelled');
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel this appointment');
    } finally {
      setBusyId(null);
    }
  };

  const canCancelAppointment = (row: TodayConsult) => {
    if (!row.appointment_id) return false;
    if (row.status === 'appointment_cancelled' || row.status === 'registration_cancelled' || row.status === 'cancelled' || row.status === 'completed') return false;
    if (isDesk) return row.status === 'scheduled';
    return row.status === 'scheduled' || row.status === 'arrived' || row.status === 'in_consult';
  };

  const cancelRegistration = async (patient: Patient) => {
    const label = (patient.mrd_number || '').startsWith('TMP-') ? `temporary id ${patient.mrd_number}` : (patient.mrd_number || patient.name);
    if (!window.confirm(`Cancel the registration for ${patient.name} (${label})?`)) return;
    setBusyId(patient.id);
    setError('');
    try {
      await api.cancelRegistration(patient.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel this registration');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Patients</h2>
          <p className="page-subtitle">{isDesk ? 'Search finds every doctor’s patients. Choose who to register the visit under.' : 'Search records and open a chart'}</p>
        </div>
        <Link to="/patients/new" className="btn btn-primary"><i className="fas fa-plus me-1"></i>Add Patient</Link>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      {showToday && (
      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
          <div>
            <h5 className="mb-0">Today’s doctor list</h5>
            <div className="small text-muted">The doctor consults from this list. Ordered tests go to billing. Prescriptions go to pharmacy.</div>
          </div>
          {isDesk && <div className="d-flex gap-2">
            <select className="form-select form-select-sm" value={kind} onChange={e => setKind(e.target.value)} aria-label="Visit">
              <option value="new">New</option>
              <option value="revisit">Revisit</option>
            </select>
            <select className="form-select form-select-sm" value={channel} onChange={e => setChannel(e.target.value)} aria-label="Source">
              <option value="walk_in">Walk-in</option>
              <option value="in_clinic">In clinic</option>
              <option value="online">Online</option>
            </select>
          </div>}
        </div>
        <div className="table-responsive">
          <table className="table mb-0">
            <thead>
              <tr><th>Patient</th><th>Visit</th><th>Source</th><th>Status</th><th>Token</th><th></th></tr>
            </thead>
            <tbody>
              {queue.length === 0 ? (
                <tr><td colSpan={6} className="text-center text-muted py-3">No one is with the doctor yet today.</td></tr>
              ) : queue.map(row => (
                <tr key={`${row.patient_id}-${row.appointment_id || 'reg'}`} className={row.status === 'appointment_cancelled' || row.status === 'registration_cancelled' ? 'text-muted' : undefined}>
                  <td>
                    <Link to={`/patients/${row.patient_id}`} className="text-decoration-none">{row.patient_name}</Link>
                  </td>
                  <td>{row.kind === 'revisit' ? 'Revisit' : 'New'}</td>
                  <td>{sourceLabel(row.channel)}</td>
                  <td>{statusLabel(row.status)}</td>
                  <td>{row.token_number || '—'}</td>
                  <td className="text-end text-nowrap">
                    {canCancelAppointment(row) && (
                      <button type="button" className="btn btn-sm btn-outline-danger me-1" disabled={busyId === row.patient_id} onClick={() => cancelAppointment(row)}>
                        Cancel appointment
                      </button>
                    )}
                    <Link to={`/patients/${row.patient_id}`} className="btn btn-sm btn-outline-primary">View</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}
      <div className="card mb-4 p-3">
        <div className="row g-2">
          <div className="col-md-3">
            <select className="form-select" value={searchType} onChange={e => setSearchType(e.target.value)}>
              <option value="name">Name</option>
              <option value="mrd">MRD Number</option>
              <option value="phone">Mobile</option>
              {!isDesk && <option value="diagnosis">Diagnosis</option>}
            </select>
          </div>
          <div className="col-md-7">
            <input className="form-control" placeholder={isDesk ? 'Search an old patient to register' : 'Search...'} value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') load(); }} />
          </div>
          <div className="col-md-2">
            <button className="btn btn-outline-primary w-100" onClick={load}>Search</button>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead><tr><th>MRD</th><th>Name</th><th>Age</th><th>Sex</th><th>Contact</th>{isDesk && <th>Doctor</th>}<th></th></tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={isDesk ? 7 : 6} className="text-center">Loading...</td></tr>
              ) : patients.length === 0 ? (
                <tr><td colSpan={isDesk ? 7 : 6} className="text-center text-muted">No patients found</td></tr>
              ) : patients.map(p => (
                <tr key={p.id}>
                  <td>{p.mrd_number ? ((p.mrd_number.startsWith('TMP-') || p.registration_status === 'temporary') ? `Temp ${p.mrd_number}` : p.mrd_number) : '-'}</td>
                  <td>{p.name}</td>
                  <td>{p.age}</td>
                  <td>{p.sex}</td>
                  <td>{p.contact || '-'}</td>
                  {isDesk && <td>{doctorName(p.doctor_id) || '—'}</td>}
                  <td className="text-nowrap text-end">
                    {isDesk && (p.mrd_number || '').startsWith('TMP-') && (
                      <Link to={`/patients/${p.id}/edit`} className="btn btn-sm btn-outline-primary me-1">Register</Link>
                    )}
                    {isDesk && q.trim() && (
                      <>
                        <select
                          className="form-select form-select-sm d-inline-block me-1"
                          style={{ width: 160 }}
                          aria-label={`Assign ${p.name}`}
                          value={doctorFor(p)}
                          onChange={e => setAssignTo(current => ({ ...current, [p.id]: Number(e.target.value) }))}
                        >
                          <option value="">Assign to…</option>
                          {doctors.map(d => (
                            <option key={d.id} value={d.id}>Dr. {d.doctor_name}</option>
                          ))}
                        </select>
                        <button type="button" className="btn btn-sm btn-primary me-1" disabled={busyId === p.id} onClick={() => sendToDoctor(p)}>
                          {queuedIds.has(p.id) ? 'Bill again' : 'Register visit'}
                        </button>
                      </>
                    )}
                    {isDesk && ((p.mrd_number || '').startsWith('TMP-') || p.registration_status === 'temporary') && (
                      <button type="button" className="btn btn-sm btn-outline-danger me-1" disabled={busyId === p.id} onClick={() => cancelRegistration(p)}>
                        Cancel registration
                      </button>
                    )}
                    <Link to={`/patients/${p.id}`} className="btn btn-sm btn-outline-primary">View</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
