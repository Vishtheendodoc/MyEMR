import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';

const empty = { mrd_number: '', name: '', age: '', sex: 'Male', contact: '', address: '' };

export default function PatientForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (id) {
      api.patient(Number(id)).then(p => setForm({
        mrd_number: p.mrd_number || '', name: p.name, age: p.age, sex: p.sex,
        contact: p.contact || '', address: p.address || '',
      }));
    }
  }, [id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = {
        ...form,
        age: String(form.age),
        mrd_number: form.mrd_number.trim() || null,
      };
      if (isEdit) {
        await api.updatePatient(Number(id), payload);
        navigate(`/patients/${id}`);
      } else {
        const p = await api.createPatient(payload);
        navigate(`/patients/${p.id}/visits/new`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="mb-4">{isEdit ? 'Edit Patient' : 'Register New Patient'}</h2>
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="card p-4">
        <form onSubmit={handleSubmit}>
          <div className="row">
            {[
              { key: 'mrd_number', label: 'MRD Number' },
              { key: 'name', label: 'Name', required: true },
              { key: 'age', label: 'Age', required: true },
              { key: 'contact', label: 'Contact' },
            ].map(f => (
              <div className="col-md-6 mb-3" key={f.key}>
                <label className="form-label">{f.label}</label>
                <input className="form-control" required={f.required}
                  value={form[f.key as keyof typeof form]}
                  onChange={e => setForm({ ...form, [f.key]: e.target.value.trimStart() })} />
              </div>
            ))}
            <div className="col-md-6 mb-3">
              <label className="form-label">Sex</label>
              <select className="form-select" value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })}>
                <option>Male</option><option>Female</option><option>Other</option>
              </select>
            </div>
            <div className="col-12 mb-3">
              <label className="form-label">Address</label>
              <textarea className="form-control" rows={2} value={form.address}
                onChange={e => setForm({ ...form, address: e.target.value })} />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Register & New Visit'}
          </button>
        </form>
      </div>
    </div>
  );
}
