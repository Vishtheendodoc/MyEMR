import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, Bill, BillingVisitOption, ClinicProfile, PriceItem } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { printBillInvoice, printCreditNote } from '../utils/printBill';
import { clinicDayKey, clinicTodayKey, formatClinicDate } from '../utils/clinicTime';
import { collectionBody } from '../utils/payments';
import { LockedDayNotice } from '../components/LockedDayNotice';
import PriceSuggest, { PriceSuggestion } from '../components/PriceSuggest';

const PAYMENT_METHODS = ['Cash', 'UPI', 'Card', 'Cheque', 'Bank Transfer'];
const GST_OPTIONS = [0, 5, 12, 18];

type DraftLine = { description: string; code: string; qty: string; rate: string; gst: string };
type InvoiceDraft = {
  title: string;
  visit_id: string;
  lines: DraftLine[];
  discount: string;
  method: string;
  payAmount: string;
  secondAmount: string;
  secondMethod: string;
};

function formatInr(n: number) {
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function formatDate(iso?: string) {
  return formatClinicDate(iso);
}

function dayKey(iso?: string) {
  return clinicDayKey(iso);
}

function todayKey() {
  return clinicTodayKey();
}

function splitTests(text: string) {
  const parts = text
    .split(/\r?\n|,|;|•/)
    .map(line => line.replace(/^[\s\-*\d.)]+/, '').trim())
    .filter(Boolean);
  return parts.length ? parts : (text.trim() ? [text.trim()] : []);
}

function findServicePrice(prices: PriceItem[], name: string) {
  const key = name.trim().toLowerCase();
  return prices.find(p => (p.kind === 'service' || p.kind === 'panel') && p.name.toLowerCase() === key);
}

function lineFromTestName(prices: PriceItem[], name: string): DraftLine {
  const item = findServicePrice(prices, name);
  return {
    description: name,
    code: item?.code || '999316',
    qty: '1',
    rate: item ? String(item.rate) : '',
    gst: item ? String(item.gst_percent || 0) : '0',
  };
}

function waPhone(contact: string) {
  const digits = contact.replace(/\D/g, '');
  if (digits.length === 10) return `91${digits}`;
  if (digits.length === 12 && digits.startsWith('91')) return digits;
  return digits || '';
}

function consultationLine(prices: PriceItem[], visitType: string): DraftLine {
  const revisit = /revisit|follow/i.test(visitType || '');
  const consult = prices.find(p => p.kind === 'service' && p.name.toLowerCase().includes(revisit ? 'follow' : 'new'))
    || prices.find(p => p.kind === 'service' && /consult/i.test(p.name));
  if (!consult) return { description: 'Consultation', code: '999312', qty: '1', rate: '', gst: '0' };
  return {
    description: consult.name,
    code: consult.code || '999312',
    qty: '1',
    rate: String(consult.rate),
    gst: String(consult.gst_percent || 0),
  };
}

function blankLine(): DraftLine {
  return { description: '', code: '', qty: '1', rate: '', gst: '0' };
}

function lineAmount(line: DraftLine) {
  const base = (Number(line.qty) || 0) * (Number(line.rate) || 0);
  return base + (base * (Number(line.gst) || 0)) / 100;
}

function dueOf(bill: Bill) {
  return Math.max(0, bill.amount - (bill.amount_paid || 0));
}

function isConsultationBill(bill: Bill) {
  const category = (bill.category || '').toLowerCase();
  if (category === 'visit' || category === 'consultation') return true;
  return (bill.description || '').toLowerCase().includes('consultation');
}

export default function Billing() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const requestedVisit = searchParams.get('visit');
  const openedVisit = useRef<string | null>(null);
  const canOpenDay = user?.role === 'doctor' || user?.role === 'admin';
  const isRegistration = user?.role === 'registration';
  const [bills, setBills] = useState<Bill[]>([]);
  const [visitOptions, setVisitOptions] = useState<BillingVisitOption[]>([]);
  const [orders, setOrders] = useState<Awaited<ReturnType<typeof api.billingOrders>>>([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('open');
  const [todayOnly, setTodayOnly] = useState(false);
  const [visitQuery, setVisitQuery] = useState('');
  const [draft, setDraft] = useState<InvoiceDraft | null>(null);
  const [collect, setCollect] = useState<{ bill: Bill; amount: string; method: string; secondAmount: string; secondMethod: string } | null>(null);
  const [clinic, setClinic] = useState<ClinicProfile | null>(null);
  const [prices, setPrices] = useState<PriceItem[]>([]);
  const [pricesReady, setPricesReady] = useState(false);
  const [refund, setRefund] = useState<{ bill: Bill; amount: string; reason: string } | null>(null);

  const load = async () => {
    try {
      const [billList, visits, orderList] = await Promise.all([
        api.bills(),
        api.billingVisitOptions(),
        api.billingOrders(),
      ]);
      setBills(billList);
      setVisitOptions(visits);
      setOrders(orderList);
      api.clinicProfile().then(setClinic).catch(() => {});
      api.prices().then(setPrices).catch(() => {}).finally(() => setPricesReady(true));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load billing data');
    }
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!requestedVisit || !pricesReady || openedVisit.current === requestedVisit) return;
    const visit = visitOptions.find(item => String(item.visit_id) === requestedVisit);
    if (!visit) return;
    openedVisit.current = requestedVisit;
    setDraft({
      title: `Consultation — ${visit.patient_name}`,
      visit_id: requestedVisit,
      lines: [consultationLine(prices, visit.visit_type)],
      discount: '',
      method: 'Cash',
      payAmount: '',
      secondAmount: '',
      secondMethod: 'UPI',
    });
    setError('');
  }, [requestedVisit, visitOptions, prices, pricesReady]);

  const activeBills = bills.filter(b => b.payment_status !== 'cancelled' && b.payment_status !== 'refunded' && (!isRegistration || isConsultationBill(b)));
  const today = todayKey();
  const summary = useMemo(() => {
    const todays = activeBills.filter(b => dayKey(b.created_at) === today);
    return {
      billed: todays.reduce((sum, b) => sum + b.amount, 0),
      collected: todays.reduce((sum, b) => sum + (b.amount_paid || 0), 0),
      outstanding: activeBills.reduce((sum, b) => sum + dueOf(b), 0),
      invoices: todays.length,
    };
  }, [bills, today]);

  const visibleBills = activeBills.filter(b => {
    if (todayOnly && dayKey(b.created_at) !== today) return false;
    if (status === 'open' && dueOf(b) <= 0) return false;
    if (status !== 'all' && status !== 'open' && b.payment_status !== status) return false;
    const haystack = `${b.invoice_number || ''} ${b.patient_name || ''} ${b.patient_mrd || ''} ${b.description}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  const draftTotal = draft
    ? Math.max(0, draft.lines.reduce((sum, line) => sum + lineAmount(line), 0) - (Number(draft.discount) || 0))
    : 0;

  const openNewInvoice = () => {
    setDraft({
      title: 'New invoice',
      visit_id: '',
      lines: [blankLine()],
      discount: '',
      method: 'Cash',
      payAmount: '',
      secondAmount: '',
      secondMethod: 'UPI',
    });
    setVisitQuery('');
    setError('');
  };

  const openOrderBill = (order: (typeof orders)[0]) => {
    const lines = splitTests(order.investigation || '').map(name => lineFromTestName(prices, name));
    setDraft({
      title: `Invoice — ${order.patient_name}`,
      visit_id: String(order.visit_id),
      lines: lines.length ? lines : [blankLine()],
      discount: '',
      method: 'Cash',
      payAmount: '',
      secondAmount: '',
      secondMethod: 'UPI',
    });
    setError('');
  };

  const updateLine = (index: number, patch: Partial<DraftLine>) => {
    setDraft(current => current && ({
      ...current,
      lines: current.lines.map((line, i) => i === index ? { ...line, ...patch } : line),
    }));
  };

  const saveInvoice = async (markPaid: boolean) => {
    if (!draft) return;
    if (!draft.visit_id) {
      setError('Select the visit this invoice belongs to.');
      return;
    }
    const lines = draft.lines.filter(line => line.description.trim() && Number(line.rate) > 0);
    if (!lines.length) {
      setError('Add at least one item with a price.');
      return;
    }
    const second = markPaid ? 0 : Number(draft.secondAmount) || 0;
    const primary = markPaid ? draftTotal : Number(draft.payAmount) || 0;
    const payNow = Math.min(primary + second, draftTotal);
    setLoading(true);
    setError('');
    try {
      const bill = await api.createBill({
        visit_id: Number(draft.visit_id),
        append_to_visit: true,
        discount_amount: Number(draft.discount) || 0,
        payment_method: draft.method,
        payment_status: payNow >= draftTotal && draftTotal > 0 ? 'paid' : 'pending',
        amount_paid: payNow,
        ...collectionBody(Math.min(primary, draftTotal), draft.method, second, draft.secondMethod),
        line_items: lines.map(line => ({
          description: line.description.trim(),
          procedure_code: line.code || null,
          quantity: Number(line.qty) || 1,
          rate: Number(line.rate),
          gst_percent: Number(line.gst) || 0,
        })),
      });
      setDraft(null);
      setSuccess(`Invoice ${bill.invoice_number || bill.id} raised for ${bill.patient_name}.`);
      printBillInvoice(bill, clinic?.name || 'Endo Clinic', user?.doctor_name, clinic || undefined);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to raise invoice');
    } finally {
      setLoading(false);
    }
  };

  const saveCollection = async () => {
    if (!collect) return;
    const second = Number(collect.secondAmount) || 0;
    const adding = (Number(collect.amount) || 0) + second;
    if (!adding || adding <= 0) {
      setError('Enter the amount received.');
      return;
    }
    const paid = Math.min((collect.bill.amount_paid || 0) + adding, collect.bill.amount);
    setLoading(true);
    setError('');
    try {
      const bill = await api.updateBill(collect.bill.id, {
        amount_paid: paid,
        payment_method: collect.method,
        ...collectionBody(Number(collect.amount) || 0, collect.method, second, collect.secondMethod),
      });
      setCollect(null);
      setSuccess(`Recorded ${formatInr(adding)} for ${bill.invoice_number || bill.id}.`);
      printBillInvoice(bill, clinic?.name || 'Endo Clinic', user?.doctor_name, clinic || undefined);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record payment');
    } finally {
      setLoading(false);
    }
  };

  const saveRefund = async () => {
    if (!refund) return;
    setLoading(true);
    setError('');
    try {
      const amount = Number(refund.amount);
      const bill = await api.updateBill(refund.bill.id, { refund_amount: amount, refund_reason: refund.reason });
      setRefund(null);
      setSuccess('Refund recorded.');
      if (amount > 0) {
        printCreditNote(bill, amount, refund.reason, clinic?.name || 'Endo Clinic', clinic || undefined);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refund');
    } finally {
      setLoading(false);
    }
  };

  const sendInvoiceWhatsApp = async (bill: Bill) => {
    setError('');
    try {
      const result = await api.whatsappInvoice(bill.id);
      if (result.whatsapp_url) {
        window.open(result.whatsapp_url, '_blank');
        return;
      }
    } catch {
      /* fall through to manual link */
    }
    const phone = waPhone(bill.patient_contact || '');
    const text = `Invoice ${bill.invoice_number || bill.id} — ${bill.patient_name} — Total ${formatInr(bill.amount)} — Paid ${formatInr(bill.amount_paid || 0)}`;
    if (phone) {
      window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, '_blank');
    } else {
      setError('No patient mobile on file for WhatsApp.');
    }
  };

  const cancelBill = async (bill: Bill) => {
    if (!window.confirm(`Cancel invoice ${bill.invoice_number || bill.id}? It will leave today's collection.`)) return;
    setError('');
    try {
      await api.updateBill(bill.id, { payment_status: 'cancelled' });
      setSuccess('Invoice cancelled.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel invoice');
    }
  };

  const priceSuggestions: PriceSuggestion[] = prices
    .filter(p => p.kind === 'service' || p.kind === 'panel')
    .map(p => ({
      label: p.name,
      detail: p.kind === 'panel' ? 'Panel' : 'Service',
      code: p.code || (p.kind === 'panel' ? '999316' : ''),
      rate: String(p.rate || ''),
      gst: String(p.gst_percent || 0),
    }));

  const visitChoices = visitOptions.filter(v => {
    const q = visitQuery.trim().toLowerCase();
    if (!q) return true;
    return `${v.patient_name} ${v.patient_mrd || ''}`.toLowerCase().includes(q);
  }).slice(0, 8);
  const selectedVisit = visitOptions.find(v => String(v.visit_id) === draft?.visit_id);

  return (
    <div>
      <div className="page-header d-flex justify-content-between align-items-start gap-3">
        <div>
          <h2>{isRegistration ? 'Consultation billing' : 'Billing'}</h2>
          <p className="page-subtitle">{isRegistration ? 'Collect the consultation fee for a visit. Type an item to see the price list.' : 'One invoice per visit, with items, discount, part-payment, and a daily collection sheet'}</p>
        </div>
        <div className="d-flex gap-2 flex-wrap">
          {!isRegistration && <Link to="/day-close" className="btn btn-outline-secondary">Day close</Link>}
          {!isRegistration && <Link to="/finance" className="btn btn-outline-secondary">Finance</Link>}
          <button type="button" className="btn btn-primary" onClick={openNewInvoice}>{isRegistration ? 'Bill consultation' : 'New invoice'}</button>
        </div>
      </div>

      {error && !draft && !collect && !refund && <div className="alert alert-danger">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="row mb-4">
        <div className="col-md-3"><div className="card p-3 text-center"><h4>{formatInr(summary.billed)}</h4><small className="text-muted">Billed today · {summary.invoices}</small></div></div>
        <div className="col-md-3"><div className="card p-3 text-center"><h4 className="text-success">{formatInr(summary.collected)}</h4><small className="text-muted">Collected today</small></div></div>
        <div className="col-md-3"><div className="card p-3 text-center"><h4 className="text-warning">{formatInr(summary.outstanding)}</h4><small className="text-muted">Outstanding</small></div></div>
        {!isRegistration && <div className="col-md-3"><div className="card p-3 text-center"><h4>{orders.filter(o => !o.billed).length}</h4><small className="text-muted">Orders to bill</small></div></div>}
      </div>

      {!isRegistration && <div className="card mb-4">
        <div className="card-header d-flex justify-content-between">
          <h5 className="mb-0">Doctor-ordered investigations</h5>
          <span className="badge badge-soft">{orders.filter(o => !o.billed).length} pending</span>
        </div>
        <div className="table-responsive">
          <table className="table mb-0 align-middle">
            <thead><tr><th>Date</th><th>Patient</th><th>Tests</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {orders.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-muted py-3">No ordered investigations yet. The doctor adds one test per line on the visit.</td></tr>
              ) : orders.map(o => (
                <tr key={o.visit_id}>
                  <td>{formatDate(o.visit_date)}</td>
                  <td>
                    <div className="fw-semibold">{o.patient_name}</div>
                    <div className="small text-muted">{o.patient_mrd || '—'}</div>
                  </td>
                  <td className="small">
                    <ul className="mb-0 ps-3">
                      {splitTests(o.investigation || '').map(test => <li key={test}>{test}</li>)}
                    </ul>
                  </td>
                  <td>{o.billed ? <span className="badge bg-success">Billed</span> : <span className="badge bg-warning text-dark">To bill</span>}</td>
                  <td>
                    {!o.billed && (
                      <button type="button" className="btn btn-sm btn-primary" onClick={() => openOrderBill(o)}>Raise bill</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>}

      <div className="card">
        <div className="card-header d-flex flex-wrap gap-2 align-items-center">
          <h5 className="mb-0 me-auto">Invoices</h5>
          <input className="form-control" style={{ maxWidth: 260 }} placeholder="Search patient, MRD, invoice" value={query} onChange={e => setQuery(e.target.value)} />
          <select className="form-select" style={{ maxWidth: 160 }} value={status} onChange={e => setStatus(e.target.value)}>
            <option value="open">Due</option>
            <option value="all">All</option>
            <option value="paid">Paid</option>
            <option value="partial">Part paid</option>
            <option value="pending">Unpaid</option>
          </select>
          <button type="button" className={`btn ${todayOnly ? 'btn-primary' : 'btn-outline-primary'}`} onClick={() => setTodayOnly(v => !v)}>Today</button>
        </div>
        <div className="table-responsive">
          <table className="table mb-0 align-middle">
            <thead>
              <tr>
                <th>Invoice</th><th>Patient</th><th>Items</th><th>Total</th><th>Paid</th><th>Due</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {visibleBills.length === 0 && (
                <tr><td colSpan={8} className="text-center text-muted py-4">No invoices match this view.</td></tr>
              )}
              {visibleBills.map(b => (
                <tr key={b.id}>
                  <td className="small">
                    <div className="fw-semibold">{b.invoice_number || `#${b.id}`}</div>
                    <div className="text-muted">{formatDate(b.created_at)}</div>
                  </td>
                  <td>
                    <div>{b.patient_name}</div>
                    <div className="small text-muted">{b.patient_mrd || '—'}</div>
                  </td>
                  <td className="small" style={{ maxWidth: 280 }}>{b.description}</td>
                  <td>{formatInr(b.amount)}</td>
                  <td>{formatInr(b.amount_paid || 0)}</td>
                  <td className={dueOf(b) > 0 ? 'fw-semibold' : ''}>{formatInr(dueOf(b))}</td>
                  <td>
                    <span className={`badge bg-${b.payment_status === 'paid' ? 'success' : b.payment_status === 'partial' ? 'info' : 'warning'}`}>
                      {b.payment_status}
                    </span>
                    {b.payment_method && <div className="small text-muted">{b.payment_method}</div>}
                  </td>
                  <td className="no-print">
                    <div className="d-flex gap-1">
                      <button type="button" className="btn btn-sm btn-outline-primary" title="Print" onClick={() => printBillInvoice(b, clinic?.name || 'Endo Clinic', user?.doctor_name, clinic || undefined)}>
                        <i className="fas fa-print"></i>
                      </button>
                      <button type="button" className="btn btn-sm btn-outline-success" title="WhatsApp invoice" onClick={() => sendInvoiceWhatsApp(b)}>
                        <i className="fab fa-whatsapp"></i>
                      </button>
                      {dueOf(b) > 0 && (
                        <button type="button" className="btn btn-sm btn-outline-success" onClick={() => setCollect({ bill: b, amount: String(dueOf(b)), method: b.payment_method || 'Cash', secondAmount: '', secondMethod: 'UPI' })}>
                          Collect
                        </button>
                      )}
                      {(b.amount_paid || 0) > 0 && (
                        <button type="button" className="btn btn-sm btn-outline-warning" onClick={() => setRefund({ bill: b, amount: String(b.amount_paid || 0), reason: '' })}>
                          Refund
                        </button>
                      )}
                      <button type="button" className="btn btn-sm btn-outline-danger" title="Cancel" onClick={() => cancelBill(b)}>
                        <i className="fas fa-ban"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {draft && (
        <div className="modal d-block" style={{ background: 'rgba(15, 40, 70, 0.45)' }} role="dialog">
          <div className="modal-dialog modal-lg modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">{draft.title}</h5>
                <button type="button" className="btn-close" onClick={() => setDraft(null)} aria-label="Close" />
              </div>
              {error && (
                <LockedDayNotice
                  className="alert alert-danger rounded-0 mb-0"
                  message={error}
                  day={todayKey()}
                  canOpen={canOpenDay}
                  onOpened={() => { setError(''); setSuccess('Day close opened.'); }}
                />
              )}
              <div className="modal-body">
                {!selectedVisit ? (
                  <>
                    <input className="form-control mb-2" placeholder="Search patient or MRD" value={visitQuery} onChange={e => setVisitQuery(e.target.value)} />
                    <div className="list-group mb-3" style={{ maxHeight: 180, overflow: 'auto' }}>
                      {visitChoices.map(v => (
                        <button type="button" key={v.visit_id} className="list-group-item list-group-item-action" onClick={() => {
                          setDraft({
                            ...draft,
                            visit_id: String(v.visit_id),
                            lines: draft.lines.some(item => item.description.trim()) ? draft.lines : [consultationLine(prices, v.visit_type)],
                          });
                        }}>
                          <strong>{v.patient_name}</strong> · {v.patient_mrd || 'No MRD'} · {formatDate(v.visit_date)}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <div>
                      <div className="fw-semibold">{selectedVisit.patient_name}</div>
                      <div className="small text-muted">{selectedVisit.patient_mrd || 'No MRD'} · {formatDate(selectedVisit.visit_date)} · {selectedVisit.visit_type}</div>
                    </div>
                    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setDraft({ ...draft, visit_id: '' })}>Change</button>
                  </div>
                )}

                <select className="form-select mb-3" value="" onChange={e => {
                  const item = prices.find(p => String(p.id) === e.target.value);
                  if (!item) return;
                  const line = { description: item.name, code: item.code || (item.kind === 'panel' ? '999316' : ''), qty: '1', rate: String(item.rate || ''), gst: String(item.gst_percent || 0) };
                  setDraft({
                    ...draft,
                    lines: draft.lines.some(row => !row.description.trim())
                      ? draft.lines.map(row => row.description.trim() ? row : line)
                      : [...draft.lines, line],
                  });
                }}>
                  <option value="">Add from the price list…</option>
                  {prices.filter(p => p.kind === 'service' || p.kind === 'panel').map(p => (
                    <option key={p.id} value={p.id}>{p.kind === 'panel' ? 'Panel: ' : ''}{p.name} — {formatInr(p.rate)}</option>
                  ))}
                </select>

                {draft.lines.map((line, index) => (
                  <div className="row g-2 mb-2" key={index}>
                    <div className="col-md-4">
                      <PriceSuggest
                        value={line.description}
                        placeholder="Item"
                        items={priceSuggestions}
                        onChange={text => updateLine(index, { description: text })}
                        onPick={item => updateLine(index, {
                          description: item.label,
                          code: item.code || '',
                          rate: item.rate || '',
                          gst: item.gst || '0',
                        })}
                      />
                    </div>
                    <div className="col-md-2">
                      <input className="form-control" placeholder="SAC" value={line.code} onChange={e => updateLine(index, { code: e.target.value })} />
                    </div>
                    <div className="col-md-1">
                      <input className="form-control" placeholder="Qty" value={line.qty} onChange={e => updateLine(index, { qty: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <input className="form-control" placeholder="Rate ₹" type="number" min="0" value={line.rate} onChange={e => updateLine(index, { rate: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <select className="form-select" value={line.gst} onChange={e => updateLine(index, { gst: e.target.value })}>
                        {GST_OPTIONS.map(g => <option key={g} value={g}>GST {g}%</option>)}
                      </select>
                    </div>
                    <div className="col-md-1 d-flex align-items-center justify-content-end">
                      <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => setDraft({ ...draft, lines: draft.lines.filter((_, i) => i !== index) })}>×</button>
                    </div>
                  </div>
                ))}
                <button type="button" className="btn btn-sm btn-outline-primary mb-3" onClick={() => setDraft({ ...draft, lines: [...draft.lines, blankLine()] })}>Add item</button>

                <div className="row g-2">
                  <div className="col-md-3">
                    <label className="form-label small">Discount ₹</label>
                    <input className="form-control" type="number" min="0" value={draft.discount} onChange={e => setDraft({ ...draft, discount: e.target.value })} />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label small">Collect now ₹</label>
                    <input className="form-control" type="number" min="0" placeholder="Leave blank if unpaid" value={draft.payAmount} onChange={e => setDraft({ ...draft, payAmount: e.target.value })} />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label small">Method</label>
                    <select className="form-select" value={draft.method} onChange={e => setDraft({ ...draft, method: e.target.value })}>
                      {PAYMENT_METHODS.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="col-md-3">
                    <label className="form-label small">Second amount ₹</label>
                    <input className="form-control" type="number" min="0" placeholder="Optional" value={draft.secondAmount} onChange={e => setDraft({ ...draft, secondAmount: e.target.value })} />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label small">Second method</label>
                    <select className="form-select" value={draft.secondMethod} onChange={e => setDraft({ ...draft, secondMethod: e.target.value })}>
                      {PAYMENT_METHODS.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="col-md-3 d-flex align-items-end">
                    <div className="fw-semibold pb-2">Total {formatInr(draftTotal)}</div>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline-secondary" onClick={() => setDraft(null)}>Cancel</button>
                <button type="button" className="btn btn-outline-primary" disabled={loading} onClick={() => saveInvoice(false)}>Save invoice</button>
                <button type="button" className="btn btn-primary" disabled={loading} onClick={() => saveInvoice(true)}>{loading ? 'Saving…' : 'Save and mark paid'}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {collect && (
        <div className="modal d-block" style={{ background: 'rgba(15, 40, 70, 0.45)' }} role="dialog">
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">Collect payment — {collect.bill.patient_name}</h5>
                <button type="button" className="btn-close" onClick={() => setCollect(null)} aria-label="Close" />
              </div>
              {error && (
                <LockedDayNotice
                  className="alert alert-danger rounded-0 mb-0"
                  message={error}
                  day={clinicDayKey(collect.bill.created_at)}
                  canOpen={canOpenDay}
                  onOpened={() => { setError(''); setSuccess('Day close opened. You can record the payment.'); }}
                />
              )}
              <div className="modal-body">
                <p className="mb-2">Invoice {collect.bill.invoice_number || collect.bill.id} · due {formatInr(dueOf(collect.bill))}</p>
                <label className="form-label small">Amount received</label>
                <input className="form-control mb-2" type="number" min="1" value={collect.amount} onChange={e => setCollect({ ...collect, amount: e.target.value })} />
                <label className="form-label small">Method</label>
                <select className="form-select mb-2" value={collect.method} onChange={e => setCollect({ ...collect, method: e.target.value })}>
                  {PAYMENT_METHODS.map(m => <option key={m}>{m}</option>)}
                </select>
                <label className="form-label small">Second amount, if the patient paid two ways</label>
                <div className="row g-2">
                  <div className="col-7">
                    <input className="form-control" type="number" min="0" placeholder="Optional" value={collect.secondAmount} onChange={e => setCollect({ ...collect, secondAmount: e.target.value })} />
                  </div>
                  <div className="col-5">
                    <select className="form-select" value={collect.secondMethod} onChange={e => setCollect({ ...collect, secondMethod: e.target.value })}>
                      {PAYMENT_METHODS.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>
                </div>
                <div className="small text-muted mt-2">Enter less than the due amount to record a part payment. The receipt shows the balance.</div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline-secondary" onClick={() => setCollect(null)}>Cancel</button>
                <button type="button" className="btn btn-primary" disabled={loading} onClick={saveCollection}>{loading ? 'Saving…' : 'Record and print'}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {refund && (
        <div className="modal d-block" style={{ background: 'rgba(15, 40, 70, 0.45)' }} role="dialog">
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">Refund — {refund.bill.invoice_number || refund.bill.id}</h5>
                <button type="button" className="btn-close" onClick={() => setRefund(null)} aria-label="Close" />
              </div>
              {error && (
                <LockedDayNotice
                  className="alert alert-danger rounded-0 mb-0"
                  message={error}
                  day={clinicDayKey(refund.bill.created_at)}
                  canOpen={canOpenDay}
                  onOpened={() => { setError(''); setSuccess('Day close opened. You can record the refund.'); }}
                />
              )}
              <div className="modal-body">
                <label className="form-label small">Amount</label>
                <input className="form-control mb-2" type="number" min="1" value={refund.amount} onChange={e => setRefund({ ...refund, amount: e.target.value })} />
                <label className="form-label small">Reason</label>
                <input className="form-control" value={refund.reason} onChange={e => setRefund({ ...refund, reason: e.target.value })} />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline-secondary" onClick={() => setRefund(null)}>Cancel</button>
                <button type="button" className="btn btn-warning" disabled={loading} onClick={saveRefund}>Record refund</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
