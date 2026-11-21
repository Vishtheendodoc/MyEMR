import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, Patient360Snapshot } from '../api/client';
import { parseUtcInstant } from '../utils/clinicTime';

const SERIES_COLORS = ['#1a6bb5', '#0a4f8c', '#b7791f', '#1f7a4c', '#c0392b'];

function formatDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Date(year, month - 1, day).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatWhen(value: string | null | undefined) {
  if (!value) return '—';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDateOnly(value);
  const parsed = parseUtcInstant(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function doseText(med: Patient360Snapshot['overview']['current_medications'][number]) {
  const clock = [med.dose_morning, med.dose_afternoon, med.dose_evening].some(Boolean)
    ? [med.dose_morning || '—', med.dose_afternoon || '—', med.dose_evening || '—'].join(' / ')
    : null;
  return [med.dosage, clock, med.frequency, med.timing, med.duration].filter(Boolean).join(' · ');
}

export default function Patient360() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Patient360Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setData(null);
    setError(null);
    api.patient360(Number(id))
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load Patient 360'));
  }, [id]);

  if (error) {
    return (
      <div className="alert alert-danger">
        {error}
        <div className="mt-2"><Link to="/patients">Back to patients</Link></div>
      </div>
    );
  }
  if (!data) return <div className="text-center py-5 text-muted">Loading Patient 360…</div>;

  const { overview, comparison } = data;
  const recorded = data.parameters.filter(item => item.latest);
  const missing = data.parameters.filter(item => !item.latest);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{overview.name}</h2>
          <p className="page-subtitle">
            Patient 360 · {overview.mrd_number ? `MRD ${overview.mrd_number}` : 'No MRD'} · {overview.age} · {overview.sex}
            {overview.visit_count === 1 ? ' · 1 visit' : ` · ${overview.visit_count} visits`}
          </p>
        </div>
        <div className="d-flex gap-2 flex-wrap">
          <Link to={`/patients/${overview.id}`} className="btn btn-outline-secondary">Chart</Link>
          <Link to={`/patients/${overview.id}/visits/new`} className="btn btn-primary">
            <i className={`fas ${overview.visit_count ? 'fa-redo' : 'fa-plus'} me-1`}></i>
            {overview.visit_count ? 'Create Revisit' : 'New Visit'}
          </Link>
        </div>
      </div>

      <p className="p360-note mb-3">{data.disclaimer}</p>

      {overview.prompts.length > 0 && (
        <div className="mb-4">
          {overview.prompts.map(prompt => (
            <div
              key={prompt.code}
              className={`alert ${prompt.severity === 'info' ? 'alert-info' : 'alert-warning'} py-2`}
              role="status"
            >
              <strong>{prompt.title}.</strong> {prompt.explanation}
              {prompt.triggering.length > 0 && (
                <div className="small mt-1">Recorded: {prompt.triggering.join(' · ')}</div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="row g-3 mb-4">
        <div className="col-lg-4">
          <div className="card h-100">
            <div className="card-header"><h5 className="mb-0">Overview</h5></div>
            <div className="card-body">
              <div className="text-muted small">Contact</div>
              <div className="mb-2">{overview.contact || '—'}</div>
              <div className="text-muted small">Address</div>
              <div className="mb-2">{overview.address || '—'}</div>
              <div className="text-muted small">Registered</div>
              <div className="mb-2">{formatWhen(overview.date_registered)}</div>
              <div className="text-muted small">Allergies</div>
              <div className="mb-2">{overview.allergies || 'None recorded'}</div>
              <div className="text-muted small">Problem list</div>
              <div className="mb-2">{overview.problem_list || '—'}</div>
              <div className="text-muted small">Comorbidities on the latest visit that recorded them</div>
              <div>{overview.comorbidities || '—'}</div>
            </div>
          </div>
        </div>
        <div className="col-lg-4">
          <div className="card h-100">
            <div className="card-header"><h5 className="mb-0">Diagnoses on record</h5></div>
            <div className="card-body">
              {overview.active_diagnoses.length === 0 ? (
                <p className="text-muted mb-0">No diagnosis text on a visit yet.</p>
              ) : (
                <ul className="mb-0 ps-3">
                  {overview.active_diagnoses.map(item => (
                    <li key={`${item.visit_id}-${item.text}`} className="mb-1">
                      <Link to={`/visits/${item.visit_id}`}>{item.text}</Link>
                      <span className="text-muted small"> · {formatDateOnly(item.visit_date)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
        <div className="col-lg-4">
          <div className="card h-100">
            <div className="card-header"><h5 className="mb-0">Medications last prescribed</h5></div>
            <div className="card-body">
              {overview.current_medications.length === 0 ? (
                <p className="text-muted mb-0">No prescription is stored on a visit.</p>
              ) : (
                <>
                  <p className="p360-note">
                    From the visit on {formatDateOnly(overview.current_medications_visit_date || '')}.
                    {overview.current_medications_visit_id && (
                      <> <Link to={`/visits/${overview.current_medications_visit_id}`}>Open visit</Link></>
                    )}
                  </p>
                  <ul className="mb-0 ps-3">
                    {overview.current_medications.map(med => (
                      <li key={`${med.drug_name}-${med.dosage}`} className="mb-2">
                        <strong>{med.drug_name}</strong>
                        {med.generic_name ? <span className="text-muted"> ({med.generic_name})</span> : null}
                        <div className="small">{doseText(med) || 'No dose recorded'}</div>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="card mb-4">
        <div className="card-header"><h5 className="mb-0">Clinical parameters</h5></div>
        <div className="card-body">
          {recorded.length === 0 ? (
            <p className="text-muted mb-0">No matching laboratory results or vitals are stored yet.</p>
          ) : (
            <div className="row g-3">
              {recorded.map(item => (
                <div className="col-sm-6 col-xl-3" key={item.code}>
                  <div className="card p360-stat">
                    <div className="label">{item.name}</div>
                    <div className="value">
                      {item.latest?.value_text}
                      {item.unit ? <span className="fs-6 fw-normal text-muted"> {item.unit}</span> : null}
                    </div>
                    <div className="meta">
                      {formatDateOnly(item.latest?.date || '')}
                      {item.latest?.source === 'calculated' ? ' · calculated' : ''}
                      {item.previous ? ` · previous ${item.previous.value_text} on ${formatDateOnly(item.previous.date)}` : ''}
                    </div>
                    {item.reference_range && <div className="meta">Reference on file: {item.reference_range}</div>}
                    {item.note && <div className="meta mt-1">{item.note}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
          {missing.length > 0 && (
            <p className="p360-note mb-0 mt-3">
              Not recorded: {missing.map(item => item.name).join(', ')}.
            </p>
          )}
        </div>
      </div>

      {(data.trends.length > 0 || data.cgm.length > 0) && (
        <div className="row g-3 mb-4">
          {data.trends.map(group => (
            <div className="col-lg-6" key={group.id}>
              <div className="card h-100 p-3">
                <h5>{group.title}</h5>
                {group.series.map((series, index) => (
                  <div key={series.code} className={index === group.series.length - 1 ? '' : 'mb-3'}>
                    <div className="small text-muted mb-1">{series.name}{series.unit ? ` (${series.unit})` : ''}</div>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={series.points}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" tickFormatter={value => formatDateOnly(String(value))} minTickGap={24} />
                        <YAxis width={42} />
                        <Tooltip labelFormatter={value => formatDateOnly(String(value))} />
                        <Line
                          type="monotone"
                          dataKey="value"
                          name={series.name}
                          stroke={SERIES_COLORS[index % SERIES_COLORS.length]}
                          dot={series.points.length < 30}
                          strokeWidth={2}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {data.cgm.length > 0 && (
            <div className="col-lg-6">
              <div className="card h-100 p-3">
                <h5>CGM glucose</h5>
                <p className="p360-note">Latest 14 days of stored readings, up to 500 points. mg/dL.</p>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={data.cgm}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" tickFormatter={value => formatWhen(String(value))} minTickGap={28} />
                    <YAxis width={42} />
                    <Tooltip labelFormatter={value => formatWhen(String(value))} />
                    <Line type="monotone" dataKey="glucose" name="Glucose" stroke="#1a6bb5" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Visit comparison</h5>
          {comparison.available && comparison.current_visit_id && (
            <Link to={`/visits/${comparison.current_visit_id}`}>Latest visit</Link>
          )}
        </div>
        <div className="card-body">
          <p className="p360-note">{comparison.disclaimer}</p>
          {!comparison.available ? (
            <p className="text-muted mb-0">At least two visits are needed before a comparison can be shown.</p>
          ) : (
            <>
              <p>
                {formatDateOnly(comparison.previous_visit_date || '')}
                {comparison.previous_visit_status ? ` (${comparison.previous_visit_status})` : ''}
                {' → '}
                {formatDateOnly(comparison.current_visit_date || '')}
                {comparison.current_visit_status ? ` (${comparison.current_visit_status})` : ''}
              </p>
              <div className="row g-3">
                <div className="col-lg-6">
                  <h6>Vitals</h6>
                  {comparison.vital_changes.length === 0 ? <p className="text-muted">No vitals on these visits.</p> : (
                    <table className="table table-sm">
                      <thead><tr><th>Measure</th><th>Earlier</th><th>Later</th><th></th></tr></thead>
                      <tbody>
                        {comparison.vital_changes.map(row => (
                          <tr key={row.code}>
                            <td>{row.name}</td>
                            <td>{row.previous_value ?? '—'}</td>
                            <td>{row.current_value ?? '—'}</td>
                            <td><span className="p360-direction">{row.direction}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
                <div className="col-lg-6">
                  <h6>Laboratory values known by each visit</h6>
                  {comparison.parameter_changes.length === 0 ? <p className="text-muted">No differing results were on file by these visit dates.</p> : (
                    <table className="table table-sm">
                      <thead><tr><th>Test</th><th>Earlier</th><th>Later</th><th></th></tr></thead>
                      <tbody>
                        {comparison.parameter_changes.map(row => (
                          <tr key={row.code}>
                            <td>{row.name}</td>
                            <td>{row.previous_value ?? '—'}{row.previous_date ? <div className="small text-muted">{formatDateOnly(row.previous_date)}</div> : null}</td>
                            <td>{row.current_value ?? '—'}{row.current_date ? <div className="small text-muted">{formatDateOnly(row.current_date)}</div> : null}</td>
                            <td><span className="p360-direction">{row.direction}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>

              <h6>Medications</h6>
              {comparison.medication_note && <p className="p360-note">{comparison.medication_note}</p>}
              {comparison.medication_changes.length === 0 && !comparison.medication_note ? (
                <p className="text-muted">No medication difference between these two visits.</p>
              ) : comparison.medication_changes.length > 0 && (
                <table className="table table-sm">
                  <thead><tr><th>Change</th><th>Medicine</th><th>Earlier</th><th>Later</th></tr></thead>
                  <tbody>
                    {comparison.medication_changes.map(row => (
                      <tr key={`${row.change}-${row.drug_name}-${row.generic_name}`}>
                        <td className="text-capitalize">{row.change}</td>
                        <td>{row.drug_name}{row.generic_name ? <span className="text-muted"> ({row.generic_name})</span> : null}</td>
                        <td>{row.previous || '—'}</td>
                        <td>{row.current || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div className="row g-3">
                <div className="col-md-6">
                  <h6>Diagnosis text</h6>
                  <p className="mb-1"><span className="text-muted">Earlier:</span> {comparison.diagnosis_previous || '—'}</p>
                  <p className="mb-1"><span className="text-muted">Later:</span> {comparison.diagnosis_current || '—'}</p>
                  {comparison.diagnoses_added.length > 0 && <p className="mb-1">Newly written: {comparison.diagnoses_added.join(', ')}</p>}
                  {comparison.diagnoses_removed.length > 0 && <p className="mb-0">Not repeated: {comparison.diagnoses_removed.join(', ')}</p>}
                </div>
                <div className="col-md-6">
                  <h6>Investigations recorded</h6>
                  <p className="mb-1"><span className="text-muted">Earlier:</span> {comparison.investigations_previous || '—'}</p>
                  <p className="mb-0"><span className="text-muted">Later:</span> {comparison.investigations_current || '—'}</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card mb-4">
        <div className="card-header"><h5 className="mb-0">Timeline</h5></div>
        <div className="card-body">
          {data.timeline.length === 0 ? (
            <p className="text-muted mb-0">Nothing is on the timeline yet.</p>
          ) : (
            <ol className="p360-timeline">
              {data.timeline.map((event, index) => (
                <li key={`${event.kind}-${event.at}-${event.ref_id ?? index}`}>
                  <div>
                    <div className="p360-kind">{event.kind.replace('_', ' ')}</div>
                    <div className="small text-muted">{/^\d{4}-\d{2}-\d{2}$/.test(event.at) ? formatDateOnly(event.at) : formatWhen(event.at)}</div>
                  </div>
                  <div>
                    <div>
                      {event.ref_type === 'visit' && event.ref_id ? (
                        <Link to={`/visits/${event.ref_id}`}>{event.title}</Link>
                      ) : event.title}
                    </div>
                    {event.detail && <div className="text-muted">{event.detail}</div>}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
