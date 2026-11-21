import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState({ display_name: '', qualifications: '', kmc_number: '' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) {
      setForm({
        display_name: user.display_name || '',
        qualifications: user.qualifications || '',
        kmc_number: user.kmc_number || '',
      });
    }
  }, [user]);

  const doctor = user?.role === 'doctor';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      await api.updateProfile(doctor ? form : { display_name: form.display_name });
      await refreshUser();
      setMessage('Profile updated successfully.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
    }
  };

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-user-md me-2"></i>Profile</h2>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="card p-4" style={{ maxWidth: 500 }}>
        <p><strong>Email:</strong> {user?.email}</p>
        <p><strong>Role:</strong> {user?.role}</p>
        <hr />
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="form-label">Display name</label>
            <input className="form-control" required value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} />
          </div>
          {doctor && (
            <>
              <div className="mb-3">
                <label className="form-label">Qualifications</label>
                <input className="form-control" value={form.qualifications} onChange={e => setForm({ ...form, qualifications: e.target.value })} />
              </div>
              <div className="mb-3">
                <label className="form-label">KMC number</label>
                <input className="form-control" value={form.kmc_number} onChange={e => setForm({ ...form, kmc_number: e.target.value })} />
              </div>
            </>
          )}
          <button type="submit" className="btn btn-primary">Update Profile</button>
        </form>
      </div>
    </div>
  );
}
