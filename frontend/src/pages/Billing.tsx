import { useEffect, useState } from 'react';
import { api, Bill } from '../api/client';

export default function Billing() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [form, setForm] = useState({ visit_id: '', description: '', amount: '', procedure_code: '' });

  const load = () => api.bills().then(setBills);
  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.createBill({
      visit_id: Number(form.visit_id),
      description: form.description,
      amount: Number(form.amount),
      procedure_code: form.procedure_code || null,
    });
    setForm({ visit_id: '', description: '', amount: '', procedure_code: '' });
    load();
  };

  const total = bills.reduce((s, b) => s + b.amount, 0);
  const paid = bills.filter(b => b.payment_status === 'paid').reduce((s, b) => s + b.amount, 0);

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-file-invoice-dollar me-2"></i>Billing</h2>
      <div className="row mb-4">
        <div className="col-md-4"><div className="card p-3 text-center"><h4>₹{total.toFixed(0)}</h4><small className="text-muted">Total Billed</small></div></div>
        <div className="col-md-4"><div className="card p-3 text-center"><h4 className="text-success">₹{paid.toFixed(0)}</h4><small className="text-muted">Collected</small></div></div>
        <div className="col-md-4"><div className="card p-3 text-center"><h4 className="text-warning">₹{(total - paid).toFixed(0)}</h4><small className="text-muted">Pending</small></div></div>
      </div>

      <div className="row">
        <div className="col-md-8 mb-4">
          <div className="card">
            <div className="table-responsive">
              <table className="table mb-0">
                <thead><tr><th>Patient</th><th>Description</th><th>Code</th><th>Amount</th><th>Status</th></tr></thead>
                <tbody>
                  {bills.map(b => (
                    <tr key={b.id}>
                      <td>{b.patient_name}</td>
                      <td>{b.description}</td>
                      <td>{b.procedure_code || '-'}</td>
                      <td>₹{b.amount}</td>
                      <td><span className={`badge bg-${b.payment_status === 'paid' ? 'success' : 'warning'}`}>{b.payment_status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card p-3">
            <h5>New Bill</h5>
            <form onSubmit={create}>
              <input className="form-control mb-2" placeholder="Visit ID" required value={form.visit_id} onChange={e => setForm({ ...form, visit_id: e.target.value })} />
              <input className="form-control mb-2" placeholder="Description" required value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              <input type="number" className="form-control mb-2" placeholder="Amount" required value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} />
              <input className="form-control mb-2" placeholder="Procedure code" value={form.procedure_code} onChange={e => setForm({ ...form, procedure_code: e.target.value })} />
              <button className="btn btn-primary w-100">Create Bill</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
