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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.updateProfile(form);
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
          {(['display_name', 'qualifications', 'kmc_number'] as const).map(f => (
            <div className="mb-3" key={f}>
              <label className="form-label text-capitalize">{f.replace('_', ' ')}</label>
              <input className="form-control" required={f === 'display_name'}
                value={form[f]} onChange={e => setForm({ ...form, [f]: e.target.value })} />
            </div>
          ))}
          <button type="submit" className="btn btn-primary">Update Profile</button>
        </form>
      </div>
    </div>
  );
}
