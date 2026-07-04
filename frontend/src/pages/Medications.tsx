import { useRef, useState } from 'react';
import { api } from '../api/client';

export default function Medications() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    try {
      const res = await api.uploadMedications(file);
      setMessage(`Uploaded ${res.generic_count} generics, ${res.brand_count} brands. Removed ${res.removed_count} stale entries.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-pills me-2"></i>Medications</h2>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="card p-4">
        <h5>Upload Medication Formulary</h5>
        <p className="text-muted">CSV or Excel with columns: generic_name, brand_name, drug_class, indication, manufacturer, strength, formulation, price</p>
        <input type="file" ref={fileRef} accept=".csv,.xlsx,.xls" className="form-control"
          onChange={handleUpload} />
      </div>
    </div>
  );
}
