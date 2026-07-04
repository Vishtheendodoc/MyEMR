import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, DashboardData } from '../api/client';

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.dashboard().then(setData).catch(e => setError(e.message));
  }, []);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!data) return <div className="text-center py-5">Loading...</div>;

  const { stats, recent_visits } = data;

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-home me-2"></i>Dashboard</h2>
      <div className="row mb-4">
        {[
          { label: 'Patients', value: stats.total_patients, icon: 'users', color: 'primary' },
          { label: 'Visits', value: stats.total_visits, icon: 'clipboard-list', color: 'success' },
          { label: 'Generic Drugs', value: stats.total_drugs, icon: 'pills', color: 'info' },
          { label: 'Brands', value: stats.total_brands, icon: 'capsules', color: 'warning' },
        ].map(s => (
          <div className="col-md-3 mb-3" key={s.label}>
            <div className="card text-center p-3">
              <i className={`fas fa-${s.icon} fa-2x text-${s.color} mb-2`}></i>
              <h3>{s.value}</h3>
              <p className="text-muted mb-0">{s.label}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-header"><h5 className="mb-0">Recent Visits</h5></div>
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead>
              <tr>
                <th>Date</th><th>Patient</th><th>MRD</th><th>Type</th><th>Diagnosis</th><th></th>
              </tr>
            </thead>
            <tbody>
              {recent_visits.length === 0 ? (
                <tr><td colSpan={6} className="text-center text-muted">No visits yet</td></tr>
              ) : recent_visits.map(v => (
                <tr key={v.id}>
                  <td>{new Date(v.visit_date).toLocaleDateString()}</td>
                  <td>{v.patient_name}</td>
                  <td>{v.patient_mrd || '-'}</td>
                  <td><span className="badge bg-secondary">{v.visit_type}</span></td>
                  <td>{v.diagnosis || '-'}</td>
                  <td><Link to={`/visits/${v.id}`} className="btn btn-sm btn-outline-primary">View</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
