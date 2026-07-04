import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { api, PatientDetail, TimelineData } from '../api/client';

export default function PatientTimeline() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    api.patient(pid).then(setPatient);
    api.timeline(pid).then(setTimeline);
  }, [id]);

  if (!patient || !timeline) return <div>Loading...</div>;

  const labKeys = Object.keys(timeline.labs);
  const firstLab = labKeys[0] ? timeline.labs[labKeys[0]] : [];

  return (
    <div>
      <div className="d-flex justify-content-between mb-4">
        <h2>Timeline — {patient.name}</h2>
        <Link to={`/patients/${patient.id}`} className="btn btn-outline-secondary">Back</Link>
      </div>
      <p className="text-muted">{timeline.visit_count} visits recorded</p>

      <div className="card mb-4 p-3">
        <h5>Vitals Trend</h5>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={timeline.vitals}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="weight" stroke="#0d6efd" name="Weight (kg)" />
            <Line type="monotone" dataKey="bmi" stroke="#198754" name="BMI" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {labKeys.map(key => (
        <div className="card mb-4 p-3" key={key}>
          <h5>{key}</h5>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={timeline.labs[key]}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke="#dc3545" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}

      {firstLab.length === 0 && timeline.vitals.length === 0 && (
        <div className="alert alert-info">No timeline data yet. Add visits and lab results.</div>
      )}
    </div>
  );
}
