import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ClinicalObservation } from '../api/client';
import { parseUtcInstant } from '../utils/clinicTime';

const COMMON_CODES = [
  { code: 'hba1c', name: 'HbA1c', unit: '%' },
  { code: 'fbs', name: 'FBS', unit: 'mg/dL' },
  { code: 'ppbs', name: 'PPBS', unit: 'mg/dL' },
  { code: 'tsh', name: 'TSH', unit: 'mIU/L' },
  { code: 'ft4', name: 'FT4', unit: 'ng/dL' },
  { code: 'creatinine', name: 'Creatinine', unit: 'mg/dL' },
  { code: 'vitamin_d', name: 'Vitamin D', unit: 'ng/mL' },
  { code: 'weight', name: 'Weight', unit: 'kg' },
];

function formatWhen(value: string) {
  const parsed = parseUtcInstant(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const hours = parsed.getUTCHours();
  const minutes = parsed.getUTCMinutes();
  const dateOnly = hours === 0 && minutes === 0 && parsed.getUTCSeconds() === 0;
  return parsed.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(dateOnly ? {} : { hour: 'numeric', minute: '2-digit', hour12: true }),
  });
}

export default function Observations() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [rows, setRows] = useState<ClinicalObservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    observation_code: 'hba1c',
    observation_name: 'HbA1c',
    value_text: '',
    unit: '%',
    observed_at: '',
    source: 'manual',
    reference_range: '',
  });

  const load = () => {
    if (!id) return;
    setError(null);
    api.observations(Number(id))
      .then(setRows)
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load observations'));
  };

  useEffect(() => { load(); }, [id]);

  const onCode = (code: string) => {
    const known = COMMON_CODES.find(item => item.code === code);
    setForm(current => ({
      ...current,
      observation_code: code,
      observation_name: known?.name || current.observation_name,
      unit: known?.unit || current.unit,
    }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!id) return;
    setError(null);
    try {
      await api.createObservation(Number(id), {
        observation_code: form.observation_code,
        observation_name: form.observation_name,
        value_text: form.value_text,
        unit: form.unit || null,
        observed_at: form.observed_at || new Date().toISOString().slice(0, 10),
        source: form.source,
        reference_range: form.reference_range || null,
      });
      setForm(current => ({ ...current, value_text: '', reference_range: '' }));
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the observation');
    }
  };

  const verify = async (row: ClinicalObservation) => {
    setError(null);
    try {
      await api.verifyObservation(row.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not verify the observation');
    }
  };

  if (!rows && !error) return <div className="text-center py-5 text-muted">Loading observations…</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Observations</h2>
          <p className="page-subtitle">Structured results linked to the original laboratory, CGM, or visit record</p>
        </div>
        <div className="d-flex gap-2">
          <button type="button" className="btn btn-outline-secondary" onClick={() => navigate(-1)}>
            <i className="fas fa-arrow-left me-1"></i>Back
          </button>
          <Link to={`/patients/${id}`} className="btn btn-outline-primary">Chart</Link>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <p className="text-muted">
        Values already saved as labs, CGM readings, or visit measurements appear here once.
        Imported rows and laboratory-report extracts stay pending until a doctor verifies them.
        Imaging reports stay on the labs screen.
      </p>

      <form className="card mb-4" onSubmit={submit}>
        <div className="card-header"><h5 className="mb-0">Add a result</h5></div>
        <div className="card-body">
          <div className="row g-3">
            <div className="col-md-3">
              <label className="form-label" htmlFor="obs-code">Code</label>
              <input
                id="obs-code"
                className="form-control"
                list="obs-codes"
                value={form.observation_code}
                onChange={event => onCode(event.target.value)}
                required
              />
              <datalist id="obs-codes">
                {COMMON_CODES.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}
              </datalist>
            </div>
            <div className="col-md-3">
              <label className="form-label" htmlFor="obs-name">Name</label>
              <input id="obs-name" className="form-control" value={form.observation_name} onChange={event => setForm({ ...form, observation_name: event.target.value })} required />
            </div>
            <div className="col-md-2">
              <label className="form-label" htmlFor="obs-value">Value</label>
              <input id="obs-value" className="form-control" value={form.value_text} onChange={event => setForm({ ...form, value_text: event.target.value })} required />
            </div>
            <div className="col-md-2">
              <label className="form-label" htmlFor="obs-unit">Unit</label>
              <input id="obs-unit" className="form-control" value={form.unit} onChange={event => setForm({ ...form, unit: event.target.value })} />
            </div>
            <div className="col-md-2">
              <label className="form-label" htmlFor="obs-date">Date</label>
              <input id="obs-date" type="date" className="form-control" value={form.observed_at} onChange={event => setForm({ ...form, observed_at: event.target.value })} />
            </div>
            <div className="col-md-4">
              <label className="form-label" htmlFor="obs-source">Source</label>
              <select id="obs-source" className="form-select" value={form.source} onChange={event => setForm({ ...form, source: event.target.value })}>
                <option value="manual">Manual entry</option>
                <option value="imported">Imported historical result</option>
                <option value="laboratory_report">Laboratory report extract</option>
              </select>
            </div>
            <div className="col-md-4">
              <label className="form-label" htmlFor="obs-range">Reference range text</label>
              <input id="obs-range" className="form-control" placeholder="70-100" value={form.reference_range} onChange={event => setForm({ ...form, reference_range: event.target.value })} />
            </div>
            <div className="col-md-4 d-flex align-items-end">
              <button className="btn btn-primary" type="submit">Save observation</button>
            </div>
          </div>
        </div>
      </form>

      <div className="card">
        <div className="card-header d-flex justify-content-between">
          <h5 className="mb-0">Recorded observations</h5>
          <span className="badge badge-soft">{rows?.length ?? 0}</span>
        </div>
        <div className="table-responsive">
          <table className="table mb-0">
            <thead>
              <tr>
                <th>When</th>
                <th>Name</th>
                <th>Value</th>
                <th>Source</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(rows ?? []).length === 0 ? (
                <tr><td colSpan={6} className="text-center text-muted py-4">No observations yet.</td></tr>
              ) : (rows ?? []).map(row => (
                <tr key={row.id}>
                  <td>{formatWhen(row.observed_at)}</td>
                  <td>
                    {row.observation_name}
                    <div className="small text-muted">{row.observation_code}</div>
                  </td>
                  <td>{row.value_text}{row.unit ? ` ${row.unit}` : ''}</td>
                  <td>
                    {row.source.replace('_', ' ')}
                    {row.source_record_type && (
                      <div className="small text-muted">{row.source_record_type} #{row.source_record_id}</div>
                    )}
                  </td>
                  <td className="text-capitalize">{row.verification_status}</td>
                  <td className="text-end">
                    {row.verification_status === 'pending' && (
                      <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => verify(row)}>Verify</button>
                    )}
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
