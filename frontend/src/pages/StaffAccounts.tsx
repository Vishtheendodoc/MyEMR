import { useEffect, useState } from 'react';
import { api, User } from '../api/client';
import { ROLE_LABELS } from '../utils/roles';

const DESK_ROLES = [
  { id: 'registration', label: 'Registration desk' },
  { id: 'billing', label: 'Billing desk' },
  { id: 'pharmacy', label: 'Pharmacy' },
  { id: 'nurse', label: 'Nurse' },
];

const EMPTY = { display_name: '', email: '', password: '', role: 'registration' };

export default function StaffAccounts() {
  const [accounts, setAccounts] = useState<User[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [passwords, setPasswords] = useState<Record<number, string>>({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const rows = await api.staffAccounts();
    setAccounts(rows);
  };

  useEffect(() => {
    load().catch(err => setError(err instanceof Error ? err.message : 'Failed to load accounts'));
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      const created = await api.createStaff(form);
      setForm(EMPTY);
      setSuccess(`${created.display_name} can sign in on the ${ROLE_LABELS[created.role] || created.role} login with ${created.email}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = async (account: User) => {
    const next = account.is_active === false;
    setError('');
    setSuccess('');
    try {
      await api.setStaffActive(account.id, next);
      setSuccess(`${account.display_name || account.email} is now ${next ? 'active' : 'inactive'}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update account status');
    }
  };

  const resetPassword = async (account: User) => {
    const password = (passwords[account.id] || '').trim();
    setError('');
    setSuccess('');
    if (password.length < 6) {
      setError('New password must be at least 6 characters.');
      return;
    }
    try {
      await api.resetStaffPassword(account.id, password);
      setPasswords(current => ({ ...current, [account.id]: '' }));
      setSuccess(`Password updated for ${account.display_name || account.email}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update password');
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Desk logins</h2>
          <p className="page-subtitle">Add registration, billing, and pharmacy accounts. They see the same clinic patients.</p>
        </div>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="row">
        <div className="col-lg-7 mb-4">
          <div className="card">
            <div className="card-header"><h5 className="mb-0">Existing accounts</h5></div>
            <div className="table-responsive">
              <table className="table mb-0 align-middle">
                <thead>
                  <tr><th>Name</th><th>Login</th><th>Desk</th><th>Status</th><th>New password</th></tr>
                </thead>
                <tbody>
                  {accounts.length === 0 && (
                    <tr><td colSpan={5} className="text-center text-muted py-4">No desk accounts yet.</td></tr>
                  )}
                  {accounts.map(account => (
                    <tr key={account.id}>
                      <td className="fw-semibold">{account.display_name}</td>
                      <td className="small">{account.email}</td>
                      <td>{ROLE_LABELS[account.role] || account.role}</td>
                      <td>
                        <span className={`badge bg-${account.is_active === false ? 'secondary' : 'success'}`}>
                          {account.is_active === false ? 'Inactive' : 'Active'}
                        </span>
                        <button type="button" className="btn btn-link btn-sm p-0 ms-2" onClick={() => toggleActive(account)}>
                          {account.is_active === false ? 'Reactivate' : 'Deactivate'}
                        </button>
                      </td>
                      <td>
                        <div className="d-flex gap-2">
                          <input
                            type="password"
                            className="form-control form-control-sm"
                            placeholder="At least 6 characters"
                            value={passwords[account.id] || ''}
                            onChange={e => setPasswords({ ...passwords, [account.id]: e.target.value })}
                          />
                          <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => resetPassword(account)}>
                            Save
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="col-lg-5">
          <div className="card p-3">
            <h5 className="mb-3">New desk login</h5>
            <form onSubmit={create}>
              <label className="form-label small">Name</label>
              <input className="form-control mb-2" required value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} />
              <label className="form-label small">Email</label>
              <input type="email" className="form-control mb-2" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
              <label className="form-label small">Password</label>
              <input type="password" className="form-control mb-2" required minLength={6} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
              <label className="form-label small">Desk</label>
              <select className="form-select mb-3" value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                {DESK_ROLES.map(role => <option key={role.id} value={role.id}>{role.label}</option>)}
              </select>
              <button className="btn btn-primary w-100" disabled={loading}>{loading ? 'Saving…' : 'Create login'}</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
