import { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';

export default function MedicationSafety() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [brand, setBrand] = useState('');
  const [prescriptionId, setPrescriptionId] = useState('');
  const [note, setNote] = useState('');

  const load = () => {
    if (!id) return;
    api.medicationSafety(Number(id)).then(setData);
  };

  useEffect(load, [id]);

  const requestChange = (event: FormEvent) => {
    event.preventDefault();
    api.requestSubstitution(Number(id), { prescription_id: Number(prescriptionId), requested_brand: brand, reason: note })
      .then(row => api.approveSubstitution(row.id))
      .then(result => {
        setNote(result.unchanged ? 'Approved. The prescribed medicine was not changed.' : 'Review the prescription.');
        load();
      })
      .catch(err => setNote(err.message));
  };

  if (!data) return <div>Loading...</div>;
  const lines = (data.current as { prescription_id: number; display: string; molecule: string }[]) || [];
  const duplicates = (data.duplicates as { molecule: string }[]) || [];
  const interactions = (data.drug_interactions as { recommendation: string }[]) || [];
  const renal = (data.renal_review as { recommendation: string; medicine: string }[]) || [];
  const allergies = (data.allergy_warnings as { medicine: string }[]) || [];

  return (
    <div>
      <div className="d-flex justify-content-between mb-3">
        <h2>Medication safety</h2>
        <Link to={`/patients/${id}`} className="btn btn-outline-secondary">Back</Link>
      </div>
      <p className="text-muted">Checks compare the latest prescription with the previous one. Nothing on this page rewrites a medicine.</p>
      {note && <div className="alert alert-info">{note}</div>}
      <ul>
        {duplicates.map(row => <li key={row.molecule}>Duplicate molecule: {row.molecule}</li>)}
        {interactions.map(row => <li key={row.recommendation}>{row.recommendation}</li>)}
        {renal.map(row => <li key={row.medicine}>{row.medicine}: {row.recommendation}</li>)}
        {allergies.map(row => <li key={row.medicine}>Allergy list matches {row.medicine}</li>)}
        {duplicates.length + interactions.length + renal.length + allergies.length === 0 && <li>No safety prompts on the latest prescription.</li>}
      </ul>
      <table className="table">
        <thead><tr><th>Id</th><th>Medicine</th><th>Molecule</th></tr></thead>
        <tbody>
          {lines.map(line => (
            <tr key={line.prescription_id}><td>{line.prescription_id}</td><td>{line.display}</td><td>{line.molecule}</td></tr>
          ))}
        </tbody>
      </table>
      <form className="card card-body" onSubmit={requestChange}>
        <h5>Brand substitution</h5>
        <p className="small text-muted">Approval records the decision. It does not replace the prescribed brand.</p>
        <div className="row g-2">
          <div className="col-md-3"><input className="form-control" placeholder="Prescription id" value={prescriptionId} onChange={event => setPrescriptionId(event.target.value)} required /></div>
          <div className="col-md-4"><input className="form-control" placeholder="Requested brand" value={brand} onChange={event => setBrand(event.target.value)} required /></div>
          <div className="col-md-3"><button className="btn btn-primary" type="submit">Record approval</button></div>
        </div>
      </form>
    </div>
  );
}
