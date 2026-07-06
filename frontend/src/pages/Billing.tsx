import { useEffect, useMemo, useState } from 'react';
import { api, Bill, BillingVisitOption } from '../api/client';

const INDIA_SERVICES = [
  { description: 'Consultation — New patient', sac: '999312', base: 800, gst: 0 },
  { description: 'Consultation — Follow-up', sac: '999312', base: 500, gst: 0 },
  { description: 'Consultation — Specialist review', sac: '999312', base: 1200, gst: 0 },
  { description: 'HbA1c test', sac: '999316', base: 400, gst: 0 },
  { description: 'Lipid profile', sac: '999316', base: 600, gst: 0 },
  { description: 'Thyroid profile (TSH, FT4)', sac: '999316', base: 700, gst: 0 },
  { description: 'USG pelvis', sac: '999313', base: 1200, gst: 5 },
  { description: 'DEXA scan', sac: '999313', base: 2500, gst: 5 },
  { description: 'CGM sensor', sac: '999317', base: 4500, gst: 12 },
];

const PAYMENT_METHODS = ['Cash', 'UPI', 'Card', 'Cheque', 'Bank Transfer'];
const GST_OPTIONS = [0, 5, 12, 18];

function formatInr(n: number) {
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function formatDate(iso: string) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

export default function Billing() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [visitOptions, setVisitOptions] = useState<BillingVisitOption[]>([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    visit_id: '',
    description: '',
    base_amount: '',
    gst_percent: '0',
    procedure_code: '',
    payment_status: 'pending',
    payment_method: 'Cash',
  });

  const load = async () => {
    try {
      const [billList, visits] = await Promise.all([api.bills(), api.billingVisitOptions()]);
      setBills(billList);
      setVisitOptions(visits);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load billing data');
    }
  };

  useEffect(() => { load(); }, []);

  const totals = useMemo(() => {
    const base = Number(form.base_amount) || 0;
    const gstPct = Number(form.gst_percent) || 0;
    const gstAmount = Math.round(base * gstPct) / 100;
    return { base, gstPct, gstAmount, total: base + gstAmount };
  }, [form.base_amount, form.gst_percent]);

  const summary = useMemo(() => {
    const total = bills.reduce((s, b) => s + b.amount, 0);
    const paid = bills.filter(b => b.payment_status === 'paid').reduce((s, b) => s + b.amount, 0);
    return { total, paid, pending: total - paid };
  }, [bills]);

  const applyService = (svc: typeof INDIA_SERVICES[0]) => {
    setForm(f => ({
      ...f,
      description: svc.description,
      base_amount: String(svc.base),
      gst_percent: String(svc.gst),
      procedure_code: svc.sac,
    }));
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!form.visit_id) {
      setError('Select a visit / patient.');
      return;
    }
    if (!totals.base || totals.base <= 0) {
      setError('Enter a valid amount.');
      return;
    }
    setLoading(true);
    try {
      await api.createBill({
        visit_id: Number(form.visit_id),
        description: form.description,
        base_amount: totals.base,
        gst_percent: totals.gstPct,
        gst_amount: totals.gstAmount,
        amount: totals.total,
        procedure_code: form.procedure_code || null,
        payment_status: form.payment_status,
        payment_method: form.payment_method,
      });
      setForm({
        visit_id: '',
        description: '',
        base_amount: '',
        gst_percent: '0',
        procedure_code: '',
        payment_status: 'pending',
        payment_method: 'Cash',
      });
      setSuccess('Bill created successfully.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create bill');
    } finally {
      setLoading(false);
    }
  };

  const markPaid = async (bill: Bill, method: string) => {
    setError('');
    try {
      await api.updateBill(bill.id, { payment_status: 'paid', payment_method: method });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update payment');
    }
  };

  const selectedVisit = visitOptions.find(v => String(v.visit_id) === form.visit_id);

  return (
    <div>
      <h2 className="mb-1"><i className="fas fa-file-invoice-dollar me-2"></i>Billing</h2>
      <p className="text-muted mb-4">India clinic billing — amounts in INR, GST, UPI/Cash payments, auto invoice numbers.</p>

      {error && <div className="alert alert-danger">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="row mb-4">
        <div className="col-md-4"><div className="card p-3 text-center"><h4>{formatInr(summary.total)}</h4><small className="text-muted">Total Billed</small></div></div>
        <div className="col-md-4"><div className="card p-3 text-center"><h4 className="text-success">{formatInr(summary.paid)}</h4><small className="text-muted">Collected</small></div></div>
        <div className="col-md-4"><div className="card p-3 text-center"><h4 className="text-warning">{formatInr(summary.pending)}</h4><small className="text-muted">Pending</small></div></div>
      </div>

      <div className="row">
        <div className="col-lg-8 mb-4">
          <div className="card">
            <div className="table-responsive">
              <table className="table mb-0 align-middle">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Patient</th>
                    <th>Description</th>
                    <th>SAC</th>
                    <th>Amount</th>
                    <th>GST</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {bills.length === 0 && (
                    <tr><td colSpan={8} className="text-center text-muted py-4">No bills yet. Create one using a recent visit.</td></tr>
                  )}
                  {bills.map(b => (
                    <tr key={b.id}>
                      <td className="small">{b.invoice_number || `#${b.id}`}</td>
                      <td>{b.patient_name}</td>
                      <td>{b.description}</td>
                      <td className="small">{b.procedure_code || '—'}</td>
                      <td>{formatInr(b.amount)}</td>
                      <td className="small">
                        {(b.gst_amount ?? 0) > 0 ? `${b.gst_percent}% (${formatInr(b.gst_amount!)})` : 'Exempt'}
                      </td>
                      <td>
                        <span className={`badge bg-${b.payment_status === 'paid' ? 'success' : 'warning'}`}>
                          {b.payment_status}
                        </span>
                        {b.payment_method && <div className="small text-muted">{b.payment_method}</div>}
                      </td>
                      <td>
                        {b.payment_status !== 'paid' && (
                          <div className="btn-group btn-group-sm">
                            {['UPI', 'Cash', 'Card'].map(m => (
                              <button key={m} type="button" className="btn btn-outline-success" onClick={() => markPaid(b, m)}>
                                {m}
                              </button>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="col-lg-4">
          <div className="card p-3 mb-3">
            <h5 className="mb-3">New Bill / Invoice</h5>
            <form onSubmit={create}>
              <label className="form-label small">Visit / Patient</label>
              <select
                className="form-select mb-2"
                required
                value={form.visit_id}
                onChange={e => setForm({ ...form, visit_id: e.target.value })}
              >
                <option value="">Select recent visit…</option>
                {visitOptions.map(v => (
                  <option key={v.visit_id} value={v.visit_id}>
                    {v.patient_name} ({v.patient_mrd}) — {formatDate(v.visit_date)} — {v.visit_type}
                  </option>
                ))}
              </select>
              {selectedVisit && (
                <div className="small text-muted mb-2">
                  {selectedVisit.diagnosis || 'No diagnosis recorded'}
                </div>
              )}

              <label className="form-label small">Quick service</label>
              <select
                className="form-select mb-2"
                value=""
                onChange={e => {
                  const svc = INDIA_SERVICES.find(s => s.description === e.target.value);
                  if (svc) applyService(svc);
                }}
              >
                <option value="">Choose common service…</option>
                {INDIA_SERVICES.map(s => (
                  <option key={s.description} value={s.description}>{s.description} — {formatInr(s.base)}</option>
                ))}
              </select>

              <input
                className="form-control mb-2"
                placeholder="Description"
                required
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
              />
              <div className="row g-2 mb-2">
                <div className="col-6">
                  <input
                    type="number"
                    className="form-control"
                    placeholder="Base amount (₹)"
                    required
                    min="1"
                    value={form.base_amount}
                    onChange={e => setForm({ ...form, base_amount: e.target.value })}
                  />
                </div>
                <div className="col-6">
                  <select
                    className="form-select"
                    value={form.gst_percent}
                    onChange={e => setForm({ ...form, gst_percent: e.target.value })}
                  >
                    {GST_OPTIONS.map(g => (
                      <option key={g} value={g}>GST {g}%</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="small mb-2">
                GST: {formatInr(totals.gstAmount)} · <strong>Total: {formatInr(totals.total)}</strong>
              </div>
              <input
                className="form-control mb-2"
                placeholder="SAC code (optional)"
                value={form.procedure_code}
                onChange={e => setForm({ ...form, procedure_code: e.target.value })}
              />
              <div className="row g-2 mb-2">
                <div className="col-6">
                  <select
                    className="form-select"
                    value={form.payment_status}
                    onChange={e => setForm({ ...form, payment_status: e.target.value })}
                  >
                    <option value="pending">Pending</option>
                    <option value="paid">Paid now</option>
                  </select>
                </div>
                <div className="col-6">
                  <select
                    className="form-select"
                    value={form.payment_method}
                    onChange={e => setForm({ ...form, payment_method: e.target.value })}
                  >
                    {PAYMENT_METHODS.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button className="btn btn-primary w-100" disabled={loading}>
                {loading ? 'Creating…' : 'Create Invoice'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
