import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, Patient } from '../api/client';

export default function Patients() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [q, setQ] = useState('');
  const [searchType, setSearchType] = useState('name');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.patients(q || undefined, searchType).then(setPatients).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2><i className="fas fa-users me-2"></i>Patients</h2>
        <Link to="/patients/new" className="btn btn-primary"><i className="fas fa-plus me-1"></i>Add Patient</Link>
      </div>
      <div className="card mb-4 p-3">
        <div className="row g-2">
          <div className="col-md-3">
            <select className="form-select" value={searchType} onChange={e => setSearchType(e.target.value)}>
              <option value="name">Name</option>
              <option value="mrd">MRD Number</option>
              <option value="diagnosis">Diagnosis</option>
            </select>
          </div>
          <div className="col-md-7">
            <input className="form-control" placeholder="Search..." value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <div className="col-md-2">
            <button className="btn btn-outline-primary w-100" onClick={load}>Search</button>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead><tr><th>MRD</th><th>Name</th><th>Age</th><th>Sex</th><th>Contact</th><th></th></tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="text-center">Loading...</td></tr>
              ) : patients.length === 0 ? (
                <tr><td colSpan={6} className="text-center text-muted">No patients found</td></tr>
              ) : patients.map(p => (
                <tr key={p.id}>
                  <td>{p.mrd_number || '-'}</td>
                  <td>{p.name}</td>
                  <td>{p.age}</td>
                  <td>{p.sex}</td>
                  <td>{p.contact || '-'}</td>
                  <td><Link to={`/patients/${p.id}`} className="btn btn-sm btn-outline-primary">View</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
