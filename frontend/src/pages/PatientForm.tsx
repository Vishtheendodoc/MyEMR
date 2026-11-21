import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, Patient, PatientDuplicateHit, User } from '../api/client';
import { useAuth } from '../hooks/useAuth';

const empty = { mrd_number: '', name: '', age: '', sex: 'Male', contact: '', address: '', allergies: '', problem_list: '' };

export default function PatientForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const isDesk = user?.role === 'registration' || user?.role === 'billing' || user?.role === 'pharmacy';
  const isEdit = Boolean(id);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [duplicates, setDuplicates] = useState<PatientDuplicateHit[]>([]);
  const [overrideDupes, setOverrideDupes] = useState(false);
  const [kind, setKind] = useState('new');
  const [channel, setChannel] = useState('walk_in');
  const [loadedTemp, setLoadedTemp] = useState(false);
  const [lookup, setLookup] = useState('');
  const [lookupType, setLookupType] = useState('name');
  const [found, setFound] = useState<Patient[]>([]);
  const [returnChannel, setReturnChannel] = useState('walk_in');
  const [registeringId, setRegisteringId] = useState<number | null>(null);
  const [doctors, setDoctors] = useState<User[]>([]);
  const [doctorId, setDoctorId] = useState<number | ''>('');

  useEffect(() => {
    if (!isDesk) return;
    api.doctors().then(list => {
      setDoctors(list);
      setDoctorId(current => current || user?.acting_doctor_id || list.find(d => d.clinic_id === user?.clinic_id)?.id || list[0]?.id || '');
    }).catch(() => setDoctors([]));
  }, [isDesk, user?.acting_doctor_id, user?.clinic_id]);

  const chosenDoctor = async () => {
    if (!isDesk) return undefined;
    if (!doctorId) throw new Error('Choose the doctor this patient is registering under');
    const id = Number(doctorId);
    await api.setActingDoctor(id);
    await refreshUser();
    return id;
  };

  useEffect(() => {
    if (id) {
      api.patient(Number(id)).then(p => {
        setLoadedTemp((p.mrd_number || '').startsWith('TMP-') || p.registration_status === 'temporary');
        setForm({
          mrd_number: p.mrd_number || '', name: p.name, age: p.age, sex: p.sex,
          contact: p.contact || '', address: p.address || '',
          allergies: p.allergies || '', problem_list: p.problem_list || '',
        });
      });
    }
  }, [id]);

  useEffect(() => {
    if (isEdit) return;
    if (!form.name.trim() && !form.contact.trim()) {
      setDuplicates([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api.checkPatientDuplicates({ name: form.name, contact: form.contact || undefined })
        .then(hits => {
          setDuplicates(hits);
          if (hits.length) setOverrideDupes(false);
        })
        .catch(() => setDuplicates([]));
    }, 400);
    return () => window.clearTimeout(timer);
  }, [form.name, form.contact, isEdit]);

  useEffect(() => {
    if (isEdit) return;
    const text = lookup.trim();
    if (text.length < 2) {
      setFound([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api.patients(text, lookupType).then(setFound).catch(() => setFound([]));
    }, 300);
    return () => window.clearTimeout(timer);
  }, [lookup, lookupType, isEdit]);

  const registerExisting = async (patientId: number) => {
    setRegisteringId(patientId);
    setError('');
    try {
      const filedUnder = await chosenDoctor();
      const queued = await api.checkInQueue({ patient_id: patientId, channel: returnChannel, kind: 'revisit', doctor_id: filedUnder });
      if (user?.role === 'registration' && queued.visit_id) navigate(`/billing?visit=${queued.visit_id}`);
      else if (user?.role === 'doctor' && queued.visit_id) navigate(`/visits/${queued.visit_id}`);
      else navigate('/patients');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not register this visit');
      setRegisteringId(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (form.contact && form.contact.length !== 10) {
      setError('Mobile number must be 10 digits');
      return;
    }
    const mobileTaken = duplicates.filter(row => row.match === 'mobile');
    if (!isEdit && mobileTaken.length > 0) {
      const taken = mobileTaken[0];
      setError(`This mobile is already registered for ${taken.name}${taken.mrd_number ? ` (${taken.mrd_number})` : ''}. Register that visit instead of a new chart.`);
      return;
    }
    if (!isEdit && duplicates.length > 0 && !overrideDupes) {
      setError('Possible duplicate patient — review matches below or choose Register anyway.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        ...form,
        age: String(form.age),
        mrd_number: form.mrd_number.trim() || null,
        allergies: form.allergies.trim() || null,
        problem_list: form.problem_list.trim() || null,
      };
      if (isEdit) {
        const typed = form.mrd_number.trim().toUpperCase();
        const payloadForSave = loadedTemp && (typed.startsWith('TMP-') || !typed)
          ? { ...payload, mrd_number: null }
          : payload;
        await api.updatePatient(Number(id), payloadForSave);
        if (loadedTemp && (typed.startsWith('TMP-') || !typed)) await api.assignMrd(Number(id));
        if (user?.role === 'registration' && loadedTemp) {
          const filedUnder = await chosenDoctor();
          const queued = await api.checkInQueue({ patient_id: Number(id), channel: 'walk_in', kind: 'new', doctor_id: filedUnder });
          if (queued.visit_id) {
            navigate(`/billing?visit=${queued.visit_id}`);
            return;
          }
        }
        navigate(`/patients/${id}`);
      } else {
        const filedUnder = await chosenDoctor();
        const p = await api.createPatient(filedUnder ? { ...payload, doctor_id: filedUnder } : payload);
        const queued = await api.checkInQueue({ patient_id: p.id, channel, kind, doctor_id: filedUnder });
        if (user?.role === 'registration' && queued.visit_id) navigate(`/billing?visit=${queued.visit_id}`);
        else if (user?.role === 'doctor' && queued.visit_id) navigate(`/visits/${queued.visit_id}`);
        else if (user?.role === 'doctor') navigate(`/patients/${p.id}/visits/new`);
        else navigate('/patients');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setLoading(false);
    }
  };

  const submitLabel = loading ? 'Saving...' : isEdit ? (loadedTemp ? 'Register and bill' : 'Update') : (user?.role === 'registration' ? 'Register and bill' : 'Register and send to doctor');

  return (
    <div>
      <h2 className="mb-4">{isEdit ? 'Edit Patient' : 'Register'}</h2>
      {error && <div className="alert alert-danger">{error}</div>}
      {isDesk && !isEdit && (
        <div className="card p-3 mb-3">
          <label className="form-label" htmlFor="register-doctor">Register under</label>
          <select
            id="register-doctor"
            className="form-select"
            required
            value={doctorId}
            onChange={e => setDoctorId(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">Choose a doctor</option>
            {doctors.map(d => (
              <option key={d.id} value={d.id}>Dr. {d.doctor_name}</option>
            ))}
          </select>
          <div className="form-text">The chart and today’s visit are filed under this doctor.</div>
        </div>
      )}
      {!isEdit && (
        <div className="card p-4 mb-4">
          <h5 className="mb-1">Returning patient</h5>
          <p className="text-muted small">Search covers every doctor’s patients. Choose who to assign the visit to, then register.</p>
          <div className="row g-2 mb-3">
            <div className="col-md-3">
              <select className="form-select" value={lookupType} onChange={e => setLookupType(e.target.value)} aria-label="Search by">
                <option value="name">Name</option>
                <option value="mrd">MRD</option>
                <option value="phone">Mobile</option>
              </select>
            </div>
            <div className="col-md-6">
              <input className="form-control" placeholder="Search old patients" value={lookup} onChange={e => setLookup(e.target.value)} />
            </div>
            <div className="col-md-3">
              <select className="form-select" value={returnChannel} onChange={e => setReturnChannel(e.target.value)} aria-label="How they came">
                <option value="walk_in">Walk-in</option>
                <option value="in_clinic">In clinic</option>
                <option value="online">Online</option>
              </select>
            </div>
          </div>
          {lookup.trim().length >= 2 && found.length === 0 && <div className="text-muted small">No matching chart.</div>}
          {found.length > 0 && (
            <div className="list-group">
              {found.slice(0, 8).map(patient => (
                <div key={patient.id} className="list-group-item d-flex justify-content-between align-items-center gap-2">
                  <div>
                    <div className="fw-semibold">{patient.name}</div>
                    <div className="small text-muted">
                      {patient.mrd_number || 'No MRD'} · {patient.age} · {patient.sex} · {patient.contact || 'No mobile'}
                      {doctors.find(d => d.id === patient.doctor_id) ? ` · Dr. ${doctors.find(d => d.id === patient.doctor_id)?.doctor_name}` : ''}
                    </div>
                  </div>
                  {user?.role === 'registration' && (
                    <select
                      className="form-select form-select-sm"
                      style={{ width: 170 }}
                      aria-label={`Assign ${patient.name}`}
                      value={doctorId}
                      onChange={e => setDoctorId(e.target.value ? Number(e.target.value) : '')}
                    >
                      <option value="">Assign to…</option>
                      {doctors.map(d => (
                        <option key={d.id} value={d.id}>Dr. {d.doctor_name}</option>
                      ))}
                    </select>
                  )}
                  <button type="button" className="btn btn-sm btn-primary" disabled={registeringId === patient.id} onClick={() => registerExisting(patient.id)}>
                    {registeringId === patient.id ? 'Registering…' : 'Register visit'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {duplicates.length > 0 && !isEdit && (
        <div className="alert alert-warning">
          <strong>{duplicates.some(row => row.match === 'mobile') ? 'This mobile is already registered' : `Possible duplicate${duplicates.length > 1 ? 's' : ''}`}:</strong>
          <ul className="mb-2 mt-2">
            {duplicates.map(d => (
              <li key={d.id} className="d-flex justify-content-between align-items-center gap-2">
                <span>
                  <Link to={`/patients/${d.id}`}>{d.name}</Link>
                  {d.mrd_number ? ` · MRD ${d.mrd_number}` : ''}
                  {d.contact ? ` · ${d.contact}` : ''}
                </span>
                {d.match === 'mobile' && (
                  <button type="button" className="btn btn-sm btn-primary" disabled={registeringId === d.id} onClick={() => registerExisting(d.id)}>
                    Register visit
                  </button>
                )}
              </li>
            ))}
          </ul>
          {!overrideDupes && !duplicates.some(row => row.match === 'mobile') && (
            <button type="button" className="btn btn-sm btn-warning" onClick={() => setOverrideDupes(true)}>
              Register anyway
            </button>
          )}
        </div>
      )}
      {!isEdit && <h5 className="mb-3">New patient</h5>}
      <div className="card p-4">
        <form onSubmit={handleSubmit}>
          <div className="row">
            <div className="col-md-6 mb-3">
              <label className="form-label">MRD Number</label>
              <input className="form-control" value={form.mrd_number}
                onChange={e => setForm({ ...form, mrd_number: e.target.value })}
                readOnly={loadedTemp} />
              <div className="form-text">
                {loadedTemp
                  ? 'Temporary booking id. Saving this registration assigns the next permanent MRD.'
                  : 'Leave blank to assign the next MRD for this year, such as MRD-2026-00021.'}
              </div>
            </div>
            {[
              { key: 'name', label: 'Name', required: true },
              { key: 'age', label: 'Age', required: true },
              { key: 'contact', label: 'Mobile (10 digits)' },
            ].map(f => (
              <div className="col-md-6 mb-3" key={f.key}>
                <label className="form-label">{f.label}</label>
                <input className="form-control" required={f.required}
                  inputMode={f.key === 'contact' ? 'numeric' : undefined}
                  maxLength={f.key === 'contact' ? 10 : undefined}
                  pattern={f.key === 'contact' ? '\\d{10}' : undefined}
                  title={f.key === 'contact' ? 'Enter a 10-digit mobile number' : undefined}
                  value={form[f.key as keyof typeof form]}
                  onChange={e => setForm({
                    ...form,
                    [f.key]: f.key === 'contact'
                      ? e.target.value.replace(/\D/g, '').slice(0, 10)
                      : e.target.value.trimStart(),
                  })} />
              </div>
            ))}
            <div className="col-md-6 mb-3">
              <label className="form-label">Sex</label>
              <select className="form-select" value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })}>
                <option>Male</option><option>Female</option><option>Other</option>
              </select>
            </div>
            <div className="col-12 mb-3">
              <label className="form-label">Address</label>
              <textarea className="form-control" rows={2} value={form.address}
                onChange={e => setForm({ ...form, address: e.target.value })} />
            </div>
            <div className="col-md-6 mb-3">
              <label className="form-label">Allergies</label>
              <textarea className="form-control" rows={2} value={form.allergies}
                onChange={e => setForm({ ...form, allergies: e.target.value })}
                placeholder="Drug/food allergies" />
            </div>
            <div className="col-md-6 mb-3">
              <label className="form-label">Problem list</label>
              <textarea className="form-control" rows={2} value={form.problem_list}
                onChange={e => setForm({ ...form, problem_list: e.target.value })}
                placeholder="Chronic conditions, active problems" />
            </div>
            {!isEdit && (
              <>
                <div className="col-md-6 mb-3">
                  <label className="form-label">Visit</label>
                  <select className="form-select" value={kind} onChange={e => setKind(e.target.value)}>
                    <option value="new">New</option>
                    <option value="revisit">Revisit</option>
                  </select>
                </div>
                <div className="col-md-6 mb-3">
                  <label className="form-label">How they came</label>
                  <select className="form-select" value={channel} onChange={e => setChannel(e.target.value)}>
                    <option value="walk_in">Walk-in</option>
                    <option value="in_clinic">In clinic</option>
                    <option value="online">Online</option>
                  </select>
                </div>
              </>
            )}
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {submitLabel}
          </button>
        </form>
      </div>
    </div>
  );
}
