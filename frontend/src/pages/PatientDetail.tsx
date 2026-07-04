import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, PatientDetail } from '../api/client';

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);

  useEffect(() => {
    if (id) api.patient(Number(id)).then(setPatient);
  }, [id]);

  if (!patient) return <div>Loading...</div>;

  return (
    <div>
      <div className="d-flex justify-content-between mb-4">
        <h2>{patient.name}</h2>
        <div>
          <Link to={`/patients/${patient.id}/edit`} className="btn btn-outline-secondary me-2">Edit</Link>
          <Link to={`/patients/${patient.id}/visits/new`} className="btn btn-primary">New Visit</Link>
        </div>
      </div>
      <div className="card mb-4 p-3">
        <div className="row">
          <div className="col-md-3"><strong>MRD:</strong> {patient.mrd_number || '-'}</div>
          <div className="col-md-2"><strong>Age:</strong> {patient.age}</div>
          <div className="col-md-2"><strong>Sex:</strong> {patient.sex}</div>
          <div className="col-md-3"><strong>Contact:</strong> {patient.contact || '-'}</div>
          <div className="col-md-12 mt-2"><strong>Address:</strong> {patient.address || '-'}</div>
        </div>
      </div>

      <div className="row mb-4">
        <div className="col-md-3"><Link to={`/patients/${patient.id}/timeline`} className="btn btn-outline-primary w-100"><i className="fas fa-chart-line me-1"></i>Timeline</Link></div>
        <div className="col-md-3"><Link to={`/patients/${patient.id}/labs`} className="btn btn-outline-primary w-100"><i className="fas fa-flask me-1"></i>Labs & Imaging</Link></div>
        <div className="col-md-3"><Link to={`/patients/${patient.id}/diabetes`} className="btn btn-outline-primary w-100"><i className="fas fa-tint me-1"></i>Diabetes</Link></div>
        <div className="col-md-3"><Link to={`/patients/${patient.id}/growth`} className="btn btn-outline-primary w-100"><i className="fas fa-child me-1"></i>Growth Chart</Link></div>
      </div>

      <div className="card">
        <div className="card-header"><h5 className="mb-0">Visit History</h5></div>
        <div className="table-responsive">
          <table className="table mb-0">
            <thead><tr><th>Date</th><th>Type</th><th>Complaints</th><th>Diagnosis</th><th></th></tr></thead>
            <tbody>
              {patient.visits.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-muted">No visits</td></tr>
              ) : patient.visits.map(v => (
                <tr key={v.id}>
                  <td>{new Date(v.visit_date).toLocaleDateString()}</td>
                  <td>{v.visit_type}</td>
                  <td>{v.chief_complaints || '-'}</td>
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
