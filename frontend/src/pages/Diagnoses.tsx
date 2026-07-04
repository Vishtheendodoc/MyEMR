import { useEffect, useRef, useState } from 'react';
import { api, Diagnosis } from '../api/client';

export default function Diagnoses() {
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = () => api.diagnoses().then(setDiagnoses).catch(e => setError(e.message));
  useEffect(() => { load(); }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await api.uploadDiagnoses(file);
      setMessage(`Uploaded ${res.count} diagnoses.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-stethoscope me-2"></i>Diagnoses</h2>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="card mb-4 p-3">
        <h5>Upload Diagnosis List</h5>
        <input type="file" ref={fileRef} accept=".csv,.xlsx,.xls" className="form-control"
          onChange={handleUpload} />
      </div>
      <div className="card">
        <div className="table-responsive">
          <table className="table mb-0">
            <thead><tr><th>Diagnosis</th><th>Category</th><th>ICD-10</th></tr></thead>
            <tbody>
              {diagnoses.length === 0 ? (
                <tr><td colSpan={3} className="text-center text-muted">No diagnoses — upload a CSV</td></tr>
              ) : diagnoses.map(d => (
                <tr key={d.id}>
                  <td>{d.diagnosis_name}</td>
                  <td>{d.category || '-'}</td>
                  <td>{d.icd_code || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
