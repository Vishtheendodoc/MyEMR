import { Fragment, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, Bill, BillingVisitOption, ClinicProfile, Prescription, PriceItem } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { printBillInvoice } from '../utils/printBill';
import { clinicDayKey, clinicTodayKey, formatClinicDate } from '../utils/clinicTime';
import { collectionBody } from '../utils/payments';
import { LockedDayNotice } from '../components/LockedDayNotice';
import PriceSuggest, { PriceSuggestion } from '../components/PriceSuggest';

const PAYMENT_METHODS = ['Cash', 'UPI', 'Card', 'Cheque', 'Bank Transfer'];
const GST_OPTIONS = [0, 5, 12, 18];
const CLINIC = 'Endo Clinic Pharmacy';

type DraftLine = { description: string; priceKey: string; code: string; qty: string; rate: string; gst: string; hint: string; note: string };
type InvoiceDraft = {
  title: string;
  visit_id: string;
  lines: DraftLine[];
  discount: string;
  method: string;
  payAmount: string;
  secondAmount: string;
  secondMethod: string;
  otc: boolean;
};
type RxVisit = Awaited<ReturnType<typeof api.pharmacyPrescriptions>>[number];
type MedPick = { key: string; label: string; hint: string; price: string };

function discountRupees(gross: number, percentText: string) {
  const percent = Math.min(100, Math.max(0, Number(percentText) || 0));
  return Math.round(gross * percent) / 100;
}

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

function drugLabel(rx: Prescription) {
  return rx.drug_name || rx.custom_drug_name || rx.generic_name || 'Medication';
}

function doseAlreadyNamed(name: string, dose: string) {
  const compact = (value: string) => value.toLowerCase().replace(/[^a-z0-9.]/g, '');
  const named = compact(name);
  const written = compact(dose);
  if (!written || written === '-') return true;
  return named.includes(written) || named.includes(written.replace(/mg$|mcg$|iu$/, ''));
}

function howToTake(rx: Prescription) {
  const name = drugLabel(rx);
  const dose = (rx.formatted_dosage || rx.dosage || '').trim();
  return [
    dose && !doseAlreadyNamed(name, dose) ? dose : '',
    rx.frequency,
    rx.timing,
    rx.duration,
  ].filter(Boolean).join(' · ');
}

function countPattern(text?: string | null) {
  if (!text || !text.includes('-')) return null;
  const parts = text.split('-').map(part => parseFloat(part.trim()));
  if (parts.length >= 2 && parts.every(value => !Number.isNaN(value) && value <= 10)) {
    return parts.reduce((sum, value) => sum + value, 0);
  }
  return null;
}

function tabletsPerDay(rx: Prescription) {
  const slots = [rx.dose_morning, rx.dose_afternoon, rx.dose_evening]
    .map(value => parseFloat(String(value || '').replace(/[^\d.]/g, '')))
    .filter(value => !Number.isNaN(value));
  if (slots.length) return slots.reduce((sum, value) => sum + value, 0) || 1;
  const fromTiming = countPattern(rx.timing);
  if (fromTiming != null) return fromTiming || 1;
  const fromDose = countPattern(rx.dosage);
  if (fromDose != null) return fromDose || 1;
  return 1;
}

function daysOf(duration?: string | null) {
  if (!duration) return 0;
  const count = parseFloat(duration);
  if (!count) return 0;
  const text = duration.toLowerCase();
  if (text.includes('week')) return count * 7;
  if (text.includes('month')) return count * 30;
  return count;
}

function suggestedQty(rx: Prescription) {
  const days = daysOf(rx.duration);
  if (!days) return '1';
  return String(Math.max(1, Math.min(999, Math.round(tabletsPerDay(rx) * days))));
}

function clinicMedicinePrice(prices: PriceItem[], name: string) {
  const key = name.trim().toLowerCase();
  const item = prices.find(p =>
    (p.kind === 'medicine' || !p.kind) && p.name.toLowerCase() === key,
  ) || prices.find(p => p.name.toLowerCase() === key);
  return item && item.rate > 0 ? String(item.rate) : '';
}

function blankLine(): DraftLine {
  return { description: '', priceKey: '', code: '300490', qty: '1', rate: '', gst: '12', hint: '', note: '' };
}

function lineFromRx(rx: Prescription, prices: PriceItem[]): DraftLine {
  const name = drugLabel(rx);
  const how = howToTake(rx);
  const priced = clinicMedicinePrice(prices, name);
  const priceRow = prices.find(p => p.name.toLowerCase() === name.trim().toLowerCase());
  const given = Number(rx.dispensed_quantity || 0);
  const asked = Number(rx.prescribed_quantity || 0);
  const pendingNote = given > 0 ? `Already dispensed ${given}${asked > 0 ? ` of ${asked}` : ''}.` : '';
  return {
    description: name,
    priceKey: name,
    code: '300490',
    qty: suggestedQty(rx),
    rate: priced,
    gst: priceRow ? String(priceRow.gst_percent ?? 12) : '12',
    hint: [how, pendingNote].filter(Boolean).join(' '),
    note: '',
  };
}

function lineAmount(line: DraftLine) {
  const base = (Number(line.qty) || 0) * (Number(line.rate) || 0);
  return base + (base * (Number(line.gst) || 0)) / 100;
}

function isPharmacyBill(bill: Bill) {
  if (bill.category === 'pharmacy') return true;
  if ((bill.description || '').toLowerCase().startsWith('pharmacy')) return true;
  return (bill.line_items || []).some(line => line.procedure_code === '300490');
}

function dueOf(bill: Bill) {
  return Math.max(0, bill.amount - (bill.amount_paid || 0));
}

export default function PharmacyBilling() {
  const { user } = useAuth();
  const canOpenDay = user?.role === 'doctor' || user?.role === 'admin';
  const [bills, setBills] = useState<Bill[]>([]);
  const [visitOptions, setVisitOptions] = useState<BillingVisitOption[]>([]);
  const [rxQueue, setRxQueue] = useState<RxVisit[]>([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [queueQuery, setQueueQuery] = useState('');
  const [declineId, setDeclineId] = useState<number | null>(null);
  const [declineNote, setDeclineNote] = useState('Patient did not buy medicines at the clinic');
  const [status, setStatus] = useState('open');
  const [todayOnly, setTodayOnly] = useState(false);
  const [visitQuery, setVisitQuery] = useState('');
  const [draft, setDraft] = useState<InvoiceDraft | null>(null);
  const [collect, setCollect] = useState<{ bill: Bill; amount: string; method: string; secondAmount: string; secondMethod: string } | null>(null);
  const [stockHints, setStockHints] = useState<Record<string, string>>({});
  const [medQuery, setMedQuery] = useState('');
  const [medResults, setMedResults] = useState<MedPick[]>([]);
  const [clinic, setClinic] = useState<ClinicProfile | null>(null);
  const [stockRows, setStockRows] = useState<Awaited<ReturnType<typeof api.stock>>>([]);
  const [stockForm, setStockForm] = useState({ item_name: '', batch_no: '', expiry_date: '', quantity: '', reorder_level: '10' });
  const [stockAction, setStockAction] = useState<{
    mode: 'return' | 'writeoff';
    item_name: string;
    quantity: string;
    batch_id: string;
  } | null>(null);
  const [expandedStock, setExpandedStock] = useState<string | null>(null);
  const [prices, setPrices] = useState<PriceItem[]>([]);

  const load = async () => {
    try {
      const [billList, visits, rx] = await Promise.all([
        api.bills(),
        api.billingVisitOptions(),
        api.pharmacyPrescriptions(),
      ]);
      setBills(billList.filter(isPharmacyBill));
      setVisitOptions(visits);
      setRxQueue(rx);
      api.clinicProfile().then(setClinic).catch(() => {});
      api.stock().then(setStockRows).catch(() => {});
      api.prices().then(rows => setPrices(rows.filter(p => p.kind === 'medicine' || p.name))).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pharmacy');
    }
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!draft) {
      setStockHints({});
      return;
    }
    const names = [...new Set(draft.lines.map(line => line.description.trim()).filter(name => name.length > 1))];
    if (!names.length) {
      setStockHints({});
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const rows = await api.stockAvailability(names);
        if (cancelled) return;
        const today = clinicTodayKey();
        const next: Record<string, string> = {};
        rows.forEach(row => {
          const saleable = (row.batches || []).filter(batch =>
            (batch.stock_status || 'saleable') === 'saleable'
            && Number(batch.quantity) > 0
            && (!batch.expiry_date || batch.expiry_date >= today),
          );
          const first = saleable[0];
          next[row.name.trim().toLowerCase()] = first
            ? `Use ${first.batch_no || 'open batch'} first · exp ${first.expiry_date || '—'} · ${first.quantity} in stock`
            : 'No saleable batch on record. Dispensing still continues for an untracked medicine.';
        });
        setStockHints(next);
      } catch {
        if (!cancelled) setStockHints({});
      }
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [draft]);

  useEffect(() => {
    if (!draft || medQuery.trim().length < 2) {
      setMedResults([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const found = await api.searchDrugs(medQuery.trim());
        const picks: MedPick[] = [];
        const seen = new Set<string>();
        const add = (key: string, label: string, hint: string, price?: number | null) => {
          if (!label || seen.has(key)) return;
          seen.add(key);
          picks.push({ key, label, hint, price: price && price > 0 ? String(price) : '' });
        };
        found.forEach(item => {
          if (item.type === 'brand' && item.brand_id) {
            add(`b-${item.brand_id}`, item.display_label || item.brand_name || item.generic_name, item.generic_name);
          }
        });
        const genericIds = [...new Set(found.map(item => item.id))].slice(0, 8);
        const brandLists = await Promise.all(genericIds.map(id => api.getBrands(id).catch(() => [])));
        if (cancelled) return;
        brandLists.forEach((brands, index) => {
          const genericName = found.find(item => item.id === genericIds[index])?.generic_name || '';
          brands.forEach(brand => add(`b-${brand.id}`, brand.display_label || brand.brand_name, genericName, brand.price));
        });
        setMedResults(picks.slice(0, 30));
      } catch {
        if (!cancelled) setMedResults([]);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [medQuery, draft]);

  const activeBills = bills.filter(b => b.payment_status !== 'cancelled');
  const today = todayKey();
  const summary = useMemo(() => {
    const todays = activeBills.filter(b => dayKey(b.created_at) === today);
    return {
      billed: todays.reduce((sum, b) => sum + b.amount, 0),
      collected: todays.reduce((sum, b) => sum + (b.amount_paid || 0), 0),
      outstanding: activeBills.reduce((sum, b) => sum + dueOf(b), 0),
    };
  }, [bills, today]);

  const medicineSuggestions = useMemo(() => {
    const byName = new Map<string, PriceSuggestion>();
    const add = (item: PriceSuggestion) => {
      const key = item.label.trim().toLowerCase();
      if (!key || byName.has(key)) return;
      byName.set(key, item);
    };
    prices.forEach(p => {
      if (p.kind === 'service' || p.kind === 'panel') return;
      add({
        label: p.name,
        detail: 'Price list',
        code: p.code || '300490',
        rate: p.rate > 0 ? String(p.rate) : '',
        gst: String(p.gst_percent ?? 12),
      });
    });
    stockRows.forEach(row => add({ label: row.item_name, detail: 'In stock', code: '300490', gst: '12' }));
    medResults.forEach(item => add({
      label: item.label,
      detail: item.hint || 'Medicine',
      code: '300490',
      rate: item.price || '',
      gst: '12',
    }));
    return [...byName.values()];
  }, [prices, stockRows, medResults]);

  const pending = rxQueue.filter(item => !item.billed && !item.declined);

  const declineRx = async (visitId: number) => {
    const note = declineNote.trim();
    if (note.length < 3) {
      setError('Add a short note for why the medicines were not dispensed.');
      return;
    }
    setError('');
    try {
      await api.declineDispense(visitId, note);
      setDeclineId(null);
      setSuccess('Dispense declined. No stock was taken.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not decline this dispense');
    }
  };
  const visibleQueue = rxQueue.filter(item => {
    const q = queueQuery.trim().toLowerCase();
    if (!q) return true;
    const drugs = item.prescriptions.map(drugLabel).join(' ');
    return `${item.patient_name} ${item.patient_mrd || ''} ${drugs}`.toLowerCase().includes(q);
  });
  const visibleBills = activeBills.filter(b => {
    if (todayOnly && dayKey(b.created_at) !== today) return false;
    if (status === 'open' && dueOf(b) <= 0) return false;
    if (status !== 'all' && status !== 'open' && b.payment_status !== status) return false;
    const haystack = `${b.invoice_number || ''} ${b.patient_name || ''} ${b.patient_mrd || ''} ${b.description}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  const draftGross = draft ? draft.lines.reduce((sum, line) => sum + lineAmount(line), 0) : 0;
  const draftDiscount = discountRupees(draftGross, draft?.discount || '');
  const draftTotal = Math.max(0, draftGross - draftDiscount);

  const openRx = (item: RxVisit) => {
    setDraft({
      title: `Dispense — ${item.patient_name}`,
      visit_id: String(item.visit_id),
      lines: item.prescriptions.map(rx => lineFromRx(rx, prices)),
      discount: '',
      method: 'UPI',
      payAmount: '',
      secondAmount: '',
      secondMethod: 'Cash',
      otc: false,
    });
    setError('');
  };

  const openNew = () => {
    setDraft({
      title: 'Walk-in medicine bill',
      visit_id: '',
      lines: [blankLine()],
      discount: '',
      method: 'UPI',
      payAmount: '',
      secondAmount: '',
      secondMethod: 'Cash',
      otc: false,
    });
    setVisitQuery('');
    setError('');
  };

  const addMedicine = (label: string, catalogPrice = '') => {
    if (!draft || !label.trim()) return;
    const line: DraftLine = {
      description: label.trim(),
      priceKey: label.trim(),
      code: '300490',
      qty: '1',
      rate: clinicMedicinePrice(prices, label) || catalogPrice,
      gst: '12',
      hint: '',
      note: '',
    };
    setDraft({
      ...draft,
      lines: draft.lines.some(item => !item.description.trim())
        ? draft.lines.map(item => item.description.trim() ? item : line)
        : [...draft.lines, line],
    });
    setMedQuery('');
    setMedResults([]);
  };

  const updateLine = (index: number, patch: Partial<DraftLine>) => {
    setDraft(current => current && ({
      ...current,
      lines: current.lines.map((line, i) => {
        if (i !== index) return line;
        const next = { ...line, ...patch };
        if (patch.description != null && !line.priceKey) next.priceKey = patch.description;
        return next;
      }),
    }));
  };

  const saveInvoice = async (markPaid: boolean) => {
    if (!draft) return;
    if (!draft.visit_id && !draft.otc) {
      setError('Select the patient visit, or mark this as an OTC sale.');
      return;
    }
    const lines = draft.lines.filter(line => line.description.trim() && Number(line.rate) > 0);
    if (!lines.length) {
      setError('Enter a rate for at least one medicine. Leave the rate blank to skip a medicine you do not have.');
      return;
    }
    const second = markPaid ? 0 : Number(draft.secondAmount) || 0;
    const primary = markPaid ? draftTotal : Number(draft.payAmount) || 0;
    const payNow = Math.min(primary + second, draftTotal);
    setLoading(true);
    setError('');
    try {
      const payload = {
        category: 'pharmacy',
        discount_amount: draftDiscount,
        payment_method: draft.method,
        payment_status: payNow >= draftTotal && draftTotal > 0 ? 'paid' : 'pending',
        amount_paid: payNow,
        ...collectionBody(Math.min(primary, draftTotal), draft.method, second, draft.secondMethod),
        line_items: lines.map(line => ({
          description: line.description.trim(),
          procedure_code: line.code || '300490',
          quantity: Number(line.qty) || 1,
          rate: Number(line.rate),
          gst_percent: Number(line.gst) || 0,
          ...(line.note.trim() ? { note: line.note.trim() } : {}),
        })),
      };
      const bill = draft.otc
        ? await api.walkInSale(payload)
        : await api.createBill({ ...payload, visit_id: Number(draft.visit_id), append_to_visit: true });
      setDraft(null);
      setSuccess(`Pharmacy invoice ${bill.invoice_number || bill.id} raised for ${bill.patient_name}.`);
      printBillInvoice(bill, clinic?.name || CLINIC, user?.doctor_name, clinic || undefined);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to raise pharmacy bill');
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
      printBillInvoice(bill, clinic?.name || CLINIC, user?.doctor_name, clinic || undefined);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record payment');
    } finally {
      setLoading(false);
    }
  };

  const cancelBill = async (bill: Bill) => {
    if (!window.confirm(`Cancel pharmacy invoice ${bill.invoice_number || bill.id}? The prescription returns to the queue.`)) return;
    setError('');
    try {
      await api.updateBill(bill.id, { payment_status: 'cancelled' });
      setSuccess('Pharmacy invoice cancelled.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel invoice');
    }
  };

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
          <h2>Pharmacy</h2>
          <p className="page-subtitle">Dispense each prescribed medicine on its own line, with quantity, price, and payment</p>
        </div>
        <div className="d-flex gap-2">
          <Link to="/stock-desk" className="btn btn-outline-secondary">Stock desk</Link>
          <button type="button" className="btn btn-primary" onClick={openNew}>Walk-in bill</button>
        </div>
      </div>

      {error && !draft && !collect && !stockAction && <div className="alert alert-danger">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="card mb-4">
        <div className="card-header d-flex flex-wrap gap-2 align-items-center">
          <h5 className="mb-0 me-auto">Stock</h5>
          {stockRows.some(r => r.messy) && (
            <button
              type="button"
              className="btn btn-sm btn-outline-warning"
              onClick={async () => {
                try {
                  const res = await api.consolidateStock();
                  setStockRows(await api.stock());
                  setSuccess(`Cleaned ${res.items_cleaned} medicine${res.items_cleaned === 1 ? '' : 's'} — RETURN rows merged.`);
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Could not clean stock');
                }
              }}
            >
              Clean up batches
            </button>
          )}
        </div>
        <div className="card-body">
          <form className="row g-2 mb-3" onSubmit={async e => {
            e.preventDefault();
            setError('');
            try {
              await api.addStock({
                item_name: stockForm.item_name.trim(),
                batch_no: stockForm.batch_no.trim() || undefined,
                expiry_date: stockForm.expiry_date || undefined,
                quantity: Number(stockForm.quantity),
                reorder_level: Number(stockForm.reorder_level) || 10,
              });
              setStockForm({ item_name: '', batch_no: '', expiry_date: '', quantity: '', reorder_level: '10' });
              setStockRows(await api.stock());
              setSuccess('Stock received.');
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to receive stock');
            }
          }}>
            <div className="col-md-3"><input className="form-control" required placeholder="Medicine name" value={stockForm.item_name} onChange={e => setStockForm({ ...stockForm, item_name: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Batch no." value={stockForm.batch_no} onChange={e => setStockForm({ ...stockForm, batch_no: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" type="date" value={stockForm.expiry_date} onChange={e => setStockForm({ ...stockForm, expiry_date: e.target.value })} title="Expiry" /></div>
            <div className="col-md-2"><input className="form-control" required type="number" min="1" step="1" placeholder="Qty" value={stockForm.quantity} onChange={e => setStockForm({ ...stockForm, quantity: e.target.value })} /></div>
            <div className="col-md-1"><input className="form-control" type="number" min="0" title="Reorder level" value={stockForm.reorder_level} onChange={e => setStockForm({ ...stockForm, reorder_level: e.target.value })} /></div>
            <div className="col-md-2"><button className="btn btn-outline-primary w-100">Receive</button></div>
          </form>
          <p className="small text-muted mb-3">Same batch number tops up that batch. Patient returns add back to the latest open batch — they no longer create RETURN spam lines.</p>
          {stockRows.length === 0 ? <div className="text-muted small">No stock recorded yet. Dispensing still works until you receive a batch.</div> : (
            <div className="table-responsive">
              <table className="table table-sm mb-0 align-middle">
                <thead><tr><th>Medicine</th><th>On hand</th><th>Batches</th><th className="text-end">Actions</th></tr></thead>
                <tbody>
                  {stockRows.map(row => {
                    const openBatches = row.batches.filter(b => Number(b.quantity) > 0);
                    const summary = openBatches.length
                      ? openBatches.slice(0, 2).map(b => `${b.batch_no || 'open'}${b.expiry_date ? ` · exp ${b.expiry_date}` : ''} (${b.quantity})`).join(' · ')
                      : '—';
                    const more = openBatches.length > 2 ? ` +${openBatches.length - 2}` : '';
                    const open = expandedStock === row.item_name;
                    return (
                      <Fragment key={row.item_name}>
                        <tr className={row.low ? 'table-warning' : ''}>
                          <td>
                            <button type="button" className="btn btn-link btn-sm p-0 text-start" onClick={() => setExpandedStock(open ? null : row.item_name)}>
                              {row.item_name}
                            </button>
                            {row.low && <span className="badge bg-warning text-dark ms-2">Low</span>}
                            {row.messy && <span className="badge bg-secondary ms-1">Needs cleanup</span>}
                          </td>
                          <td className="fw-semibold">{row.quantity}</td>
                          <td className="small text-muted">{summary}{more}</td>
                          <td className="text-end text-nowrap">
                            <button
                              type="button"
                              className="btn btn-sm btn-outline-success me-1"
                              title="Patient returned medicine"
                              onClick={() => setStockAction({ mode: 'return', item_name: row.item_name, quantity: '1', batch_id: openBatches[0] ? String(openBatches[0].id) : '' })}
                            >
                              Return in
                            </button>
                            <button
                              type="button"
                              className="btn btn-sm btn-outline-danger"
                              title="Write-off or supplier return"
                              onClick={() => setStockAction({ mode: 'writeoff', item_name: row.item_name, quantity: '1', batch_id: openBatches[0] ? String(openBatches[0].id) : '' })}
                            >
                              Write-off
                            </button>
                          </td>
                        </tr>
                        {open && (
                          <tr>
                            <td colSpan={4} className="bg-light">
                              <table className="table table-sm mb-0">
                                <thead><tr><th>Batch</th><th>Expiry</th><th>Qty</th><th></th></tr></thead>
                                <tbody>
                                  {row.batches.map(b => (
                                    <tr key={b.id}>
                                      <td>{b.batch_no || (b.synthetic ? 'Merged/open' : '—')}</td>
                                      <td>{b.expiry_date || '—'}{b.expired ? ' · expired' : ''}</td>
                                      <td>{b.quantity}</td>
                                      <td className="text-end">
                                        {Number(b.quantity) > 0 && (
                                          <>
                                            <button type="button" className="btn btn-sm btn-link" onClick={() => setStockAction({ mode: 'return', item_name: row.item_name, quantity: '1', batch_id: String(b.id) })}>Return in</button>
                                            <button type="button" className="btn btn-sm btn-link text-danger" onClick={() => setStockAction({ mode: 'writeoff', item_name: row.item_name, quantity: '1', batch_id: String(b.id) })}>Write-off</button>
                                          </>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {stockAction && (
        <div className="modal d-block" style={{ background: 'rgba(15, 40, 70, 0.45)' }} role="dialog">
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">{stockAction.mode === 'return' ? 'Patient return → stock' : 'Write-off / supplier return'}</h5>
                <button type="button" className="btn-close" onClick={() => setStockAction(null)} aria-label="Close" />
              </div>
              {error && <div className="alert alert-danger rounded-0 mb-0">{error}</div>}
              <div className="modal-body">
                <p className="mb-2"><strong>{stockAction.item_name}</strong></p>
                <label className="form-label small">Quantity</label>
                <input className="form-control mb-3" type="number" min="1" step="1" value={stockAction.quantity} onChange={e => setStockAction({ ...stockAction, quantity: e.target.value })} />
                <label className="form-label small">Batch (optional)</label>
                <select className="form-select" value={stockAction.batch_id} onChange={e => setStockAction({ ...stockAction, batch_id: e.target.value })}>
                  <option value="">Auto (FEFO / latest open)</option>
                  {(stockRows.find(r => r.item_name === stockAction.item_name)?.batches || [])
                    .filter(b => stockAction.mode === 'return' || Number(b.quantity) > 0)
                    .map(b => (
                      <option key={b.id} value={b.id}>{b.batch_no || 'open'} · {b.expiry_date || 'no expiry'} · qty {b.quantity}</option>
                    ))}
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-light" onClick={() => setStockAction(null)}>Cancel</button>
                <button
                  type="button"
                  className={`btn ${stockAction.mode === 'return' ? 'btn-success' : 'btn-danger'}`}
                  onClick={async () => {
                    const qty = Number(stockAction.quantity);
                    if (!qty || qty <= 0) {
                      setError('Enter a quantity');
                      return;
                    }
                    try {
                      const batch_id = stockAction.batch_id ? Number(stockAction.batch_id) : undefined;
                      if (stockAction.mode === 'return') {
                        await api.returnStock(stockAction.item_name, { quantity: qty, batch_id });
                        setSuccess(`Returned ${qty} of ${stockAction.item_name} to stock.`);
                      } else {
                        await api.writeOffStock(stockAction.item_name, { quantity: qty, batch_id });
                        setSuccess(`Wrote off ${qty} of ${stockAction.item_name}.`);
                      }
                      setStockAction(null);
                      setStockRows(await api.stock());
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Stock update failed');
                    }
                  }}
                >
                  {stockAction.mode === 'return' ? 'Add to stock' : 'Confirm write-off'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="row mb-4">
        <div className="col-md-3"><div className="card p-3 text-center"><h4>{formatInr(summary.billed)}</h4><small className="text-muted">Billed today</small></div></div>
        <div className="col-md-3"><div className="card p-3 text-center"><h4 className="text-success">{formatInr(summary.collected)}</h4><small className="text-muted">Collected today</small></div></div>
        <div className="col-md-3"><div className="card p-3 text-center"><h4 className="text-warning">{formatInr(summary.outstanding)}</h4><small className="text-muted">Outstanding</small></div></div>
        <div className="col-md-3"><div className="card p-3 text-center"><h4>{pending.length}</h4><small className="text-muted">Prescriptions to dispense</small></div></div>
      </div>

      <div className="card mb-4">
        <div className="card-header d-flex flex-wrap gap-2 align-items-center">
          <h5 className="mb-0 me-auto">Prescriptions from the doctor</h5>
          <input className="form-control" style={{ maxWidth: 260 }} placeholder="Search patient or medicine" value={queueQuery} onChange={e => setQueueQuery(e.target.value)} />
          <span className="badge badge-soft">{pending.length} to bill</span>
        </div>
        <div className="table-responsive">
          <table className="table mb-0 align-middle">
            <thead><tr><th>Date</th><th>Patient</th><th>Medicines</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {visibleQueue.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-muted py-4">No prescriptions to show. They appear after the doctor prescribes.</td></tr>
              ) : visibleQueue.map(item => (
                <tr key={item.visit_id}>
                  <td>{formatDate(item.visit_date)}</td>
                  <td>
                    <div className="fw-semibold">{item.patient_name}</div>
                    <div className="small text-muted">{item.patient_mrd || '—'}</div>
                  </td>
                  <td>
                    <ul className="mb-0 small ps-3">
                      {item.prescriptions.map(rx => (
                        <li key={rx.id}>
                          <strong>{drugLabel(rx)}</strong>
                          {howToTake(rx) ? ` · ${howToTake(rx)}` : ''}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td>
                    {item.declined
                      ? <span className="badge bg-secondary">Declined</span>
                      : item.billed
                        ? <span className="badge bg-success">Dispensed</span>
                        : <span className="badge bg-warning text-dark">To dispense</span>}
                    {item.dispense_note && <div className="small text-muted mt-1">{item.dispense_note}</div>}
                  </td>
                  <td>
                    {!item.billed && !item.declined && (
                      <div className="d-flex flex-wrap gap-1 justify-content-end">
                        <button type="button" className="btn btn-sm btn-primary" onClick={() => openRx(item)}>Dispense</button>
                        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => { setDeclineId(item.visit_id); setDeclineNote('Patient did not buy medicines at the clinic'); }}>Decline</button>
                      </div>
                    )}
                    {declineId === item.visit_id && (
                      <div className="mt-2" style={{ minWidth: 220 }}>
                        <textarea className="form-control form-control-sm mb-1" rows={2} value={declineNote} onChange={e => setDeclineNote(e.target.value)} />
                        <div className="d-flex gap-1">
                          <button type="button" className="btn btn-sm btn-secondary" onClick={() => declineRx(item.visit_id)}>Save decline</button>
                          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setDeclineId(null)}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header d-flex flex-wrap gap-2 align-items-center">
          <h5 className="mb-0 me-auto">Pharmacy invoices</h5>
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
              <tr><th>Invoice</th><th>Patient</th><th>Medicines</th><th>Total</th><th>Paid</th><th>Due</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {visibleBills.length === 0 && (
                <tr><td colSpan={8} className="text-center text-muted py-4">No pharmacy invoices match this view.</td></tr>
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
                  <td>
                    <div className="d-flex gap-1">
                      <button type="button" className="btn btn-sm btn-outline-primary" title="Print" onClick={() => printBillInvoice(b, clinic?.name || CLINIC, user?.doctor_name, clinic || undefined)}>
                        <i className="fas fa-print"></i>
                      </button>
                      {dueOf(b) > 0 && (
                        <button type="button" className="btn btn-sm btn-outline-success" onClick={() => setCollect({ bill: b, amount: String(dueOf(b)), method: b.payment_method || 'UPI', secondAmount: '', secondMethod: 'Cash' })}>
                          Collect
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
          <div className="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
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
                    <div className="form-check mb-2">
                      <input className="form-check-input" type="checkbox" id="otc-sale" checked={draft.otc} onChange={e => setDraft({ ...draft, otc: e.target.checked })} />
                      <label className="form-check-label" htmlFor="otc-sale">OTC sale without a patient chart</label>
                    </div>
                    {!draft.otc && <input className="form-control mb-2" placeholder="Search patient or MRD" value={visitQuery} onChange={e => setVisitQuery(e.target.value)} />}
                    {!draft.otc && (
                    <div className="list-group mb-3" style={{ maxHeight: 180, overflow: 'auto' }}>
                      {visitChoices.map(v => (
                        <button type="button" key={v.visit_id} className="list-group-item list-group-item-action" onClick={() => setDraft({ ...draft, visit_id: String(v.visit_id), otc: false })}>
                          <strong>{v.patient_name}</strong> · {v.patient_mrd || 'No MRD'} · {formatDate(v.visit_date)}
                        </button>
                      ))}
                    </div>
                    )}
                  </>
                ) : (
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <div>
                      <div className="fw-semibold">{selectedVisit.patient_name}</div>
                      <div className="small text-muted">{selectedVisit.patient_mrd || 'No MRD'} · {formatDate(selectedVisit.visit_date)}</div>
                    </div>
                    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setDraft({ ...draft, visit_id: '' })}>Change</button>
                  </div>
                )}
                <p className="small text-muted">Quantity follows the dose schedule. Search to add or substitute a medicine, and leave the rate blank to skip one you do not have.</p>
                <div className="mb-3 position-relative">
                  <input
                    className="form-control"
                    placeholder="Search generic or brand"
                    value={medQuery}
                    onChange={e => setMedQuery(e.target.value)}
                  />
                  {(medResults.length > 0 || medQuery.trim().length >= 2) && (
                    <div className="list-group position-absolute w-100 shadow-sm mt-1" style={{ zIndex: 20, maxHeight: 220, overflow: 'auto' }}>
                      {medResults.map(item => (
                        <button
                          type="button"
                          key={item.key}
                          className="list-group-item list-group-item-action py-2"
                          onClick={() => addMedicine(item.label, item.price)}
                        >
                          <div className="fw-semibold">{item.label}</div>
                          {item.hint && item.hint !== item.label && <div className="small text-muted">{item.hint}</div>}
                        </button>
                      ))}
                      {medResults.length === 0 && (
                        <button type="button" className="list-group-item list-group-item-action" onClick={() => addMedicine(medQuery.trim())}>
                          Use “{medQuery.trim()}”
                        </button>
                      )}
                    </div>
                  )}
                </div>
                {draft.lines.map((line, index) => (
                  <div className="border rounded p-2 mb-2" key={index}>
                    <div className="row g-2">
                      <div className="col-md-6">
                        <PriceSuggest
                          value={line.description}
                          placeholder="Medicine"
                          items={medicineSuggestions}
                          onChange={text => updateLine(index, { description: text, priceKey: '' })}
                          onPick={item => updateLine(index, {
                            description: item.label,
                            priceKey: item.label,
                            code: item.code || '300490',
                            rate: item.rate || clinicMedicinePrice(prices, item.label),
                            gst: item.gst || '12',
                          })}
                        />
                      </div>
                      <div className="col-md-2">
                        <input className="form-control" placeholder="Qty" value={line.qty} onChange={e => updateLine(index, { qty: e.target.value })} />
                      </div>
                      <div className="col-md-2">
                        <input className="form-control" type="number" min="0" placeholder="Rate ₹" value={line.rate} onChange={e => updateLine(index, { rate: e.target.value })} />
                      </div>
                      <div className="col-md-2 d-flex gap-1">
                        <select className="form-select" value={line.gst} onChange={e => updateLine(index, { gst: e.target.value })}>
                          {GST_OPTIONS.map(g => <option key={g} value={g}>{g}%</option>)}
                        </select>
                        <button type="button" className="btn btn-outline-danger" onClick={() => setDraft({ ...draft, lines: draft.lines.filter((_, i) => i !== index) })}>×</button>
                      </div>
                    </div>
                    {line.hint && <div className="small text-muted mt-1">{line.hint}</div>}
                    {stockHints[line.description.trim().toLowerCase()] && (
                      <div className="small text-primary mt-1">{stockHints[line.description.trim().toLowerCase()]}</div>
                    )}
                    {line.hint && (
                      <input
                        className="form-control form-control-sm mt-1"
                        placeholder="Substitution note, if this is not the prescribed brand"
                        value={line.note}
                        onChange={e => updateLine(index, { note: e.target.value })}
                      />
                    )}
                  </div>
                ))}
                <div className="row g-2">
                  <div className="col-md-3">
                    <label className="form-label small">Discount %</label>
                    <input className="form-control" type="number" min="0" max="100" placeholder="0" value={draft.discount} onChange={e => setDraft({ ...draft, discount: e.target.value })} />
                    {draftDiscount > 0 && <div className="small text-muted mt-1">Less {formatInr(draftDiscount)}</div>}
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
                    <div className="fw-semibold pb-2">
                      {draftDiscount > 0 && <div className="small text-muted fw-normal">Subtotal {formatInr(draftGross)}</div>}
                      Total {formatInr(draftTotal)}
                    </div>
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
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline-secondary" onClick={() => setCollect(null)}>Cancel</button>
                <button type="button" className="btn btn-primary" disabled={loading} onClick={saveCollection}>{loading ? 'Saving…' : 'Record and print'}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
