import { useEffect, useState } from 'react';
import { api, ClinicProfile, DayCloseSummary } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { openPrintHtml } from '../utils/openPrintHtml';
import { clinicTodayKey, formatClinicDate, formatClinicDateTime } from '../utils/clinicTime';

function formatInr(n: number) {
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function formatDate(iso?: string) {
  return formatClinicDate(iso);
}

export default function DayClose() {
  const { user } = useAuth();
  const canOpenLockedDay = user?.role === 'doctor' || user?.role === 'admin';
  const [selected, setSelected] = useState(clinicTodayKey());
  const [locks, setLocks] = useState<Array<{ date: string; locked_at?: string | null; notes?: string | null }>>([]);
  const [summary, setSummary] = useState<DayCloseSummary | null>(null);
  const [clinic, setClinic] = useState<ClinicProfile | null>(null);
  const [notes, setNotes] = useState('');
  const [openingCash, setOpeningCash] = useState('');
  const [closingCash, setClosingCash] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async (day = selected) => {
    try {
      const [s, c, lockedDays] = await Promise.all([
        api.dayCloseSummary(day),
        api.clinicProfile(),
        api.dayCloseLocks(),
      ]);
      setSummary(s);
      setClinic(c);
      setLocks(lockedDays);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load day close');
    }
  };

  useEffect(() => { load(selected); }, [selected]);

  const printDayBook = () => {
    if (!summary) return;
    const date = summary.date || new Date().toISOString().slice(0, 10);
    const opening = summary.locked ? Number(summary.opening_cash || 0) : (Number(openingCash) || 0);
    const expected = opening + Number(summary.cash || 0);
    const counted = summary.locked
      ? Number(summary.closing_cash || 0)
      : (closingCash.trim() === '' ? null : Number(closingCash) || 0);
    const rows = [
      ['Cash', summary.cash || 0],
      ['UPI', summary.upi || 0],
      ['Card', summary.card || 0],
      ['Bank', summary.bank || 0],
      ['Other', summary.other || 0],
    ];
    const html = `<!doctype html><html><head><meta charset="utf-8"/><title>Day book ${date}</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;padding:24px;max-width:520px;margin:0 auto}
table{width:100%;border-collapse:collapse;margin-top:12px}th,td{border:1px solid #ccc;padding:8px;text-align:left}
th{background:#eef5fb}.total{font-weight:700;font-size:18px;margin-top:16px}
@media print{button{display:none}}</style></head><body>
<button onclick="window.print()">Print</button>
<h2>Day book — ${date}</h2>
<p>${clinic?.name || 'Clinic'}</p>
<table><thead><tr><th>Mode</th><th style="text-align:right">Collected</th></tr></thead>
<tbody>${rows.map(([m, v]) => `<tr><td>${m}</td><td style="text-align:right">${formatInr(Number(v))}</td></tr>`).join('')}</tbody></table>
<p class="total">Billed: ${formatInr(summary.billed || 0)} · Collected: ${formatInr(summary.collected || 0)}</p>
<p>Opening cash ${formatInr(opening)} · Expected drawer ${formatInr(expected)}${counted != null ? ` · Counted ${formatInr(Number(counted))}` : ''}</p>
<script>window.addEventListener('load',()=>setTimeout(()=>window.print(),200));</script>
</body></html>`;
    openPrintHtml(html, 'Allow pop-ups to print the day book.');
  };

  const lockDay = async () => {
    if (!window.confirm('Lock this day close? Further edits may require a doctor or admin to open it.')) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const opening = Number(openingCash) || 0;
      const counted = closingCash.trim() === '' ? undefined : Number(closingCash);
      await api.lockDayClose({
        notes: notes.trim() || undefined,
        opening_cash: opening,
        closing_cash: counted,
        day: summary?.date,
      });
      setSuccess('Day close locked.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to lock day');
    } finally {
      setLoading(false);
    }
  };

  const openDay = async () => {
    if (!window.confirm('Open this locked day? Collections can be edited again.')) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await api.reopenDayClose({ day: summary?.date });
      setSuccess('Day close opened.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open day');
    } finally {
      setLoading(false);
    }
  };

  const s = summary || {};

  return (
    <div>
      <div className="page-header d-flex justify-content-between align-items-start gap-3">
        <div>
          <h2>Day close</h2>
          <p className="page-subtitle">Collections and day-book lock — {formatDate(s.date)}</p>
        </div>
        <div className="d-flex gap-2 align-items-center">
          <input className="form-control" type="date" value={selected} onChange={e => setSelected(e.target.value)} />
          <button type="button" className="btn btn-outline-primary" onClick={printDayBook} disabled={!summary}>Print day book</button>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}
      {s.locked && (
        <div className="alert alert-secondary d-flex justify-content-between align-items-center gap-3 flex-wrap">
          <div>
            <i className="fas fa-lock me-2"></i>
            Day already locked{s.locked_at ? ` at ${formatClinicDateTime(s.locked_at)}` : ''}.
            {s.notes ? <div className="small mt-1">Notes: {s.notes}</div> : null}
          </div>
          {canOpenLockedDay && (
            <button type="button" className="btn btn-outline-primary" disabled={loading} onClick={openDay}>
              {loading ? 'Opening…' : 'Open day close'}
            </button>
          )}
          {!canOpenLockedDay && <span className="small">A doctor or admin can open this day.</span>}
        </div>
      )}

      {locks.length > 0 && (
        <div className="mb-3">
          <div className="small text-muted mb-2">Locked days</div>
          {locks.map(row => (
            <button
              type="button"
              key={row.date}
              className={`btn btn-sm me-2 mb-2 ${row.date === selected ? 'btn-secondary' : 'btn-outline-secondary'}`}
              onClick={() => setSelected(row.date)}
            >
              {formatDate(row.date)}
            </button>
          ))}
        </div>
      )}

      <div className="row mb-4">
        {[
          { label: 'Cash', value: s.cash || 0 },
          { label: 'UPI', value: s.upi || 0 },
          { label: 'Card', value: s.card || 0 },
          { label: 'Bank', value: s.bank || 0 },
          { label: 'Other', value: s.other || 0 },
        ].map(item => (
          <div className="col-md col-6 mb-3" key={item.label}>
            <div className="card p-3 text-center">
              <h4>{formatInr(item.value)}</h4>
              <small className="text-muted">{item.label}</small>
            </div>
          </div>
        ))}
      </div>

      <div className="row mb-4">
        <div className="col-md-6">
          <div className="card p-3 text-center">
            <h4>{formatInr(s.billed || 0)}</h4>
            <small className="text-muted">Billed today</small>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card p-3 text-center">
            <h4 className="text-success">{formatInr(s.collected || 0)}</h4>
            <small className="text-muted">Collected today</small>
          </div>
        </div>
      </div>

      {(() => {
        const opening = s.locked ? Number(s.opening_cash || 0) : (Number(openingCash) || 0);
        const expected = opening + Number(s.cash || 0);
        const counted = s.locked ? Number(s.closing_cash || 0) : (closingCash.trim() === '' ? null : Number(closingCash) || 0);
        return (
          <div className="card p-4 mb-4">
            <h5 className="mb-3">Cash drawer</h5>
            <div className="row g-3">
              <div className="col-md-4">
                <label className="form-label small">Opening cash</label>
                {s.locked ? <div className="fw-semibold">{formatInr(opening)}</div> : (
                  <input className="form-control" type="number" min="0" value={openingCash} onChange={e => setOpeningCash(e.target.value)} placeholder="0" />
                )}
              </div>
              <div className="col-md-4">
                <label className="form-label small">Expected in drawer</label>
                <div className="fw-semibold">{formatInr(expected)}</div>
                <div className="small text-muted">Opening plus today’s cash collections</div>
              </div>
              <div className="col-md-4">
                <label className="form-label small">Counted closing cash</label>
                {s.locked ? <div className="fw-semibold">{formatInr(Number(counted || 0))}</div> : (
                  <input className="form-control" type="number" min="0" value={closingCash} onChange={e => setClosingCash(e.target.value)} placeholder="Leave blank to use the expected amount" />
                )}
                {counted != null && <div className="small text-muted mt-1">Difference {formatInr(Number(counted) - expected)}</div>}
              </div>
            </div>
          </div>
        );
      })()}

      {!s.locked && (
        <div className="card p-4">
          <h5 className="mb-3">Lock day</h5>
          <label className="form-label small">Notes (optional)</label>
          <textarea className="form-control mb-3" rows={2} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Handover notes, discrepancies…" />
          <button type="button" className="btn btn-warning" disabled={loading} onClick={lockDay}>
            {loading ? 'Locking…' : 'Lock day close'}
          </button>
        </div>
      )}
    </div>
  );
}
