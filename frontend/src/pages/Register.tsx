import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: '', password: '', display_name: '', qualifications: '', kmc_number: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.register(form);
      navigate('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="card p-4" style={{ width: '100%', maxWidth: 480 }}>
        <h3 className="text-center text-primary mb-4">Register</h3>
        {error && <div className="alert alert-danger">{error}</div>}
        <form onSubmit={handleSubmit}>
          {(['email', 'display_name', 'password', 'qualifications', 'kmc_number'] as const).map(field => (
            <div className="mb-3" key={field}>
              <label className="form-label text-capitalize">{field.replace('_', ' ')}</label>
              <input
                type={field === 'password' ? 'password' : field === 'email' ? 'email' : 'text'}
                className="form-control"
                value={form[field]}
                onChange={e => setForm({ ...form, [field]: e.target.value })}
                required={['email', 'display_name', 'password'].includes(field)}
              />
            </div>
          ))}
          <button type="submit" className="btn btn-primary w-100" disabled={loading}>Register</button>
        </form>
        <p className="text-center mt-3"><Link to="/login">Back to Login</Link></p>
      </div>
    </div>
  );
}
