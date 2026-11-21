import { useEffect, useState } from 'react';
import { api } from '../api/client';

type Finance = {
  date_from: string;
  date_to: string;
  billed: number;
  consultation: number;
  pharmacy: number;
  investigation: number;
  other: number;
  collected: number;
  outstanding: number;
  refunds: number;
  discounts: number;
  invoices: number;
  patients: number;
  average_per_patient: number;
  payments: { cash: number; upi: number; card: number; bank: number; other: number };
  note: string;
};

const RANGES = [
  ['today', 'Today'],
  ['yesterday', 'Yesterday'],
  ['week', 'This week'],
  ['month', 'This month'],
] as const;

function money(n: number) {
  return `₹${(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Finance() {
  const [preset, setPreset] = useState<string>('today');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [report, setReport] = useState<Finance | null>(null);
  const [error, setError] = useState('');

  const load = (next = preset, start = from, end = to) => {
    setError('');
    api.finance(next, start, end).then(row => setReport(row as Finance)).catch(err => setError(err.message));
  };

  useEffect(() => { load('today', '', ''); }, []);

  return (
    <div>
      <div className="page-header">
        <h2>Finance</h2>
        <p className="page-subtitle">Collections by service and payment mode. Tax splits follow the clinic setting and are not a GST return.</p>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="d-flex flex-wrap gap-2 mb-3">
        {RANGES.map(([id, label]) => (
          <button key={id} type="button" className={`btn btn-sm ${preset === id && !from ? 'btn-primary' : 'btn-outline-primary'}`} onClick={() => { setPreset(id); setFrom(''); setTo(''); load(id, '', ''); }}>{label}</button>
        ))}
        <input className="form-control form-control-sm" style={{ maxWidth: 160 }} type="date" value={from} onChange={e => setFrom(e.target.value)} />
        <input className="form-control form-control-sm" style={{ maxWidth: 160 }} type="date" value={to} onChange={e => setTo(e.target.value)} />
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => { setPreset('custom'); load('custom', from, to); }}>Custom range</button>
      </div>
      {report && (
        <>
          <p className="text-muted small">{report.date_from} to {report.date_to} · {report.invoices} invoices · {report.patients} patients · average {money(report.average_per_patient)}</p>
          <div className="row g-3 mb-3">
            {[
              ['Billed', report.billed],
              ['Consultation', report.consultation],
              ['Pharmacy', report.pharmacy],
              ['Investigations', report.investigation],
              ['Collected', report.collected],
              ['Outstanding', report.outstanding],
              ['Refunds', report.refunds],
              ['Discounts', report.discounts],
            ].map(([label, value]) => (
              <div className="col-md-3" key={String(label)}>
                <div className="card p-3"><div className="text-muted small">{label}</div><h4 className="mb-0">{money(Number(value))}</h4></div>
              </div>
            ))}
          </div>
          <div className="card">
            <div className="card-header"><h5 className="mb-0">Payment modes</h5></div>
            <table className="table mb-0">
              <tbody>
                <tr><td>Cash</td><td>{money(report.payments.cash)}</td></tr>
                <tr><td>UPI</td><td>{money(report.payments.upi)}</td></tr>
                <tr><td>Card</td><td>{money(report.payments.card)}</td></tr>
                <tr><td>Bank transfer</td><td>{money(report.payments.bank)}</td></tr>
                <tr><td>Other</td><td>{money(report.payments.other)}</td></tr>
              </tbody>
            </table>
          </div>
          <p className="small text-muted mt-3">{report.note}</p>
        </>
      )}
    </div>
  );
}
