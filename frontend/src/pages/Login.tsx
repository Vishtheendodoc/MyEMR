import { useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ROLE_HOME, ROLE_LABELS } from '../utils/roles';

const PORTALS = [
  { role: 'doctor', path: '/login/doctor', icon: 'user-md', label: 'Doctor', hint: 'Full clinical access' },
  { role: 'registration', path: '/login/registration', icon: 'id-card', label: 'Registration', hint: 'Patient registration desk' },
  { role: 'billing', path: '/login/billing', icon: 'file-invoice-dollar', label: 'Billing', hint: 'Consultation billing desk' },
  { role: 'pharmacy', path: '/login/pharmacy', icon: 'pills', label: 'Pharmacy', hint: 'Pharmacy billing desk' },
] as const;

export default function Login() {
  const { portal } = useParams<{ portal?: string }>();
  const navigate = useNavigate();
  const expectedRole = portal && ['doctor', 'registration', 'billing', 'pharmacy'].includes(portal) ? portal : null;
  const { user, login, logout } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (user && !loading) {
    return <Navigate to={ROLE_HOME[user.role] || '/'} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      const me = await api.me();
      if (expectedRole && expectedRole !== 'doctor' && me.role !== expectedRole && me.role !== 'doctor') {
        logout();
        setError(`This portal is for ${ROLE_LABELS[expectedRole]}. Your account role is ${ROLE_LABELS[me.role] || me.role}.`);
        return;
      }
      navigate(ROLE_HOME[me.role] || '/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const title = expectedRole ? ROLE_LABELS[expectedRole] : 'Endo EMR';
  return (
    <div className="auth-page">
      <div className="auth-card" style={{ maxWidth: expectedRole ? 420 : 560 }}>
        <div className="text-center mb-4">
          <div className="brand-mark">
            <i className={`fas fa-${expectedRole === 'pharmacy' ? 'pills' : expectedRole === 'billing' ? 'file-invoice-dollar' : expectedRole === 'registration' ? 'id-card' : 'heartbeat'}`}></i>
          </div>
          <h3 className="brand-display mb-1">{title}</h3>
          <p className="text-muted mb-0">
            {expectedRole ? `${ROLE_LABELS[expectedRole]} login` : 'Choose a desk portal or sign in as doctor'}
          </p>
        </div>

        {!expectedRole && (
          <div className="row g-2 mb-2">
            {PORTALS.map(p => (
              <div className="col-6" key={p.role}>
                <Link to={p.path} className="btn btn-outline-primary w-100 py-3 text-start h-100">
                  <div><i className={`fas fa-${p.icon} me-2`}></i><strong>{p.label}</strong></div>
                  <small className="text-muted">{p.hint}</small>
                </Link>
              </div>
            ))}
          </div>
        )}

        {expectedRole && (
          <>
            {error && <div className="alert alert-danger">{error}</div>}
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label className="form-label">Email</label>
                <input type="email" className="form-control" value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
              <div className="mb-3">
                <label className="form-label">Password</label>
                <input type="password" className="form-control" value={password} onChange={e => setPassword(e.target.value)} required />
              </div>
              <button type="submit" className="btn btn-primary w-100" disabled={loading}>
                {loading ? 'Signing in...' : 'Login'}
              </button>
            </form>
            <p className="text-center mt-3 mb-0">
              <Link to="/login">All portals</Link>
              {expectedRole === 'doctor' && <> · <Link to="/register">Register doctor</Link></>}
            </p>
            <p className="text-center text-muted small mb-0">Ask the doctor for a desk login if you need one.</p>
          </>
        )}
      </div>
    </div>
  );
}
