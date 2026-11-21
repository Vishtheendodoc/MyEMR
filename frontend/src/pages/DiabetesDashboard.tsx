import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api, PatientDetail } from '../api/client';
import { formatClinicClock, formatClinicDateTime } from '../utils/clinicTime';

export default function DiabetesDashboard() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [data, setData] = useState<Awaited<ReturnType<typeof api.diabetesDashboard>> | null>(null);

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    api.patient(pid).then(setPatient);
    api.diabetesDashboard(pid).then(setData);
  }, [id]);

  if (!patient || !data) return <div>Loading...</div>;

  return (
    <div>
      <div className="d-flex justify-content-between mb-4">
        <h2>Diabetes Dashboard — {patient.name}</h2>
        <Link to={`/patients/${patient.id}`} className="btn btn-outline-secondary">Back</Link>
      </div>

      {Array.isArray(data.screening) && data.screening.length > 0 && (
        <div className="card p-3 mb-4">
          <h5>Screening</h5>
          <p className="small text-muted">These reminders do not order a test or change a medicine.</p>
          <ul className="mb-0">
            {data.screening.map(item => (
              <li key={item.item}>
                {item.item.replace(/_/g, ' ')}
                {item.overdue ? ' — due' : ''}
                {item.last_on ? ` — last ${item.last_on}` : ' — no result stored'}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.cgm_metrics && (
        <div className="row mb-4">
          {[
            ['Time in range', data.cgm_metrics.time_in_range],
            ['Above range', data.cgm_metrics.time_above_range],
            ['Below range', data.cgm_metrics.time_below_range],
            ['GMI', data.cgm_metrics.gmi],
            ['CV %', data.cgm_metrics.coefficient_of_variation],
            ['Average mg/dL', data.cgm_metrics.average_glucose],
          ].map(([label, value]) => (
            <div className="col-md-2" key={String(label)}>
              <div className="card p-2 text-center">
                <strong>{value ?? '—'}</strong>
                <small className="text-muted">{label}</small>
              </div>
            </div>
          ))}
        </div>
      )}
      {data.postprandial && <p className="text-muted small">{data.postprandial.note}</p>}
      {data.nocturnal_hypoglycemia && <p>Nocturnal readings below 70 mg/dL: {data.nocturnal_hypoglycemia.count}</p>}
      {data.screening && data.screening.length > 0 && (
        <ul>
          {data.screening.map(item => <li key={item.item}>{item.item}: {item.overdue ? 'due for review' : item.last_on}</li>)}
        </ul>
      )}

      {Array.isArray(data.recent_labs) && data.recent_labs.length > 0 && (
        <div className="card p-3 mb-4">
          <h5>Results on this chart</h5>
          <table className="table mb-0">
            <thead><tr><th>Test</th><th>Value</th><th>Date</th></tr></thead>
            <tbody>
              {data.recent_labs.map(lab => (
                <tr key={lab.test_name}>
                  <td>{lab.test_name}</td>
                  <td>{lab.value} {lab.unit || ''}</td>
                  <td>{lab.result_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card mb-4 p-3">
        <h5>HbA1c Trend</h5>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data.hba1c_trend}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis domain={[4, 12]} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#dc3545" name="HbA1c %" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card mb-4 p-3">
        <h5>CGM Glucose (mg/dL)</h5>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data.cgm_readings}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" tickFormatter={t => formatClinicClock(String(t))} />
            <YAxis domain={[60, 250]} />
            <Tooltip labelFormatter={t => formatClinicDateTime(String(t))} />
            <Line type="monotone" dataKey="glucose" stroke="#0d6efd" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {data.insulin_dosing.length > 0 && (
        <div className="card p-3">
          <h5>Insulin Dosing History</h5>
          <table className="table mb-0">
            <thead><tr><th>Date</th><th>Drug</th><th>AM</th><th>PM</th><th>HS</th></tr></thead>
            <tbody>
              {data.insulin_dosing.map((d, i) => (
                <tr key={i}>
                  <td>{d.visit_date}</td>
                  <td>{d.drug}</td>
                  <td>{d.morning || '-'}</td>
                  <td>{d.afternoon || '-'}</td>
                  <td>{d.evening || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
