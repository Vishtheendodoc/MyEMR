import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, FollowUpItem } from '../api/client';

export default function FollowUpQueue() {
  const [items, setItems] = useState<FollowUpItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.followUps().then(setItems).catch(e => setError(e.message));
  }, []);

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-calendar-check me-2"></i>Follow-up Queue</h2>
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="card">
        <div className="table-responsive">
          <table className="table mb-0">
            <thead>
              <tr><th>Patient</th><th>MRD</th><th>Due Date</th><th>Overdue</th><th>Diagnosis</th><th></th></tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={6} className="text-center text-muted py-4">No overdue follow-ups</td></tr>
              ) : items.map(item => (
                <tr key={item.visit_id}>
                  <td>{item.patient_name}</td>
                  <td>{item.patient_mrd || '-'}</td>
                  <td>{new Date(item.follow_up_date).toLocaleDateString()}</td>
                  <td><span className="badge bg-danger">{item.days_overdue} days</span></td>
                  <td>{item.diagnosis || '-'}</td>
                  <td>
                    <Link to={`/patients/${item.patient_id}/visits/new`} className="btn btn-sm btn-primary me-1">New Visit</Link>
                    <Link to={`/patients/${item.patient_id}`} className="btn btn-sm btn-outline-secondary">Patient</Link>
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
