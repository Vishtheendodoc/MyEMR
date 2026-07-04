import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api, PatientDetail } from '../api/client';

export default function DiabetesDashboard() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [data, setData] = useState<{
    hba1c_trend: { date: string; value: string }[];
    cgm_readings: { time: string; glucose: number }[];
    insulin_dosing: { visit_date: string; drug: string; morning: string | null; afternoon: string | null; evening: string | null }[];
  } | null>(null);

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
            <XAxis dataKey="time" tickFormatter={t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
            <YAxis domain={[60, 250]} />
            <Tooltip labelFormatter={t => new Date(t).toLocaleString()} />
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
