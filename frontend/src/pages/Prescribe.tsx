import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, Brand, DrugSearchResult, PriceItem, VisitDetail } from '../api/client';
import SuggestField from '../components/SuggestField';
import { recallTyped, rememberTyped } from '../utils/typedMemory';
import { formatClinicDate } from '../utils/clinicTime';

const FREQUENCIES = [
  { value: 'OD', label: 'OD (Once Daily)' },
  { value: 'BD', label: 'BD (Twice Daily)' },
  { value: 'TID', label: 'TID (Three Times Daily)' },
  { value: 'QID', label: 'QID (Four Times Daily)' },
  { value: 'SOS', label: 'SOS (As Needed)' },
  { value: 'STAT', label: 'STAT (Immediately)' },
  { value: 'Weekly Once', label: 'Weekly Once' },
  { value: 'Monthly Once', label: 'Monthly Once' },
];

const MEAL_TIMING = [
  { value: '', label: '— Meal timing —' },
  { value: 'Before Food', label: 'Before Food' },
  { value: 'After Food', label: 'After Food' },
  { value: 'With Food', label: 'With Food' },
  { value: 'Empty Stomach', label: 'Empty Stomach' },
  { value: 'Bedtime', label: 'Bedtime' },
];

function buildTiming(morning: boolean, afternoon: boolean, night: boolean) {
  return `${morning ? 1 : 0}-${afternoon ? 1 : 0}-${night ? 1 : 0}`;
}

function suggestedDosage(brand: Brand | null, item?: DrugSearchResult): string {
  if (!brand) return item?.suggested_dosage || item?.strength || '';
  return brand.suggested_dosage || item?.suggested_dosage || brand.strength || item?.strength || '';
}

function FavoriteRx({ visitId, onAdded }: { visitId: number; onAdded: () => Promise<void> }) {
  const [items, setItems] = useState<PriceItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  useEffect(() => {
    api.prices().then(rows => setItems(rows.filter(row => row.kind === 'favorite'))).catch(() => {});
  }, []);
  if (!items.length) return null;
  return (
    <div className="mb-3">
      <label className="form-label">Favorite prescription</label>
      <select className="form-select" value="" disabled={busy} onChange={async e => {
        const item = items.find(row => String(row.id) === e.target.value);
        if (!item) return;
        const names = (item.detail || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        setBusy(true);
        setNote('');
        try {
          for (const name of names) {
            await api.addPrescription(visitId, {
              custom_drug_name: name,
              frequency: 'OD',
              duration: '30 days',
              timing: '1-0-0',
            });
          }
          setNote(`Added ${names.length} medicine${names.length === 1 ? '' : 's'} from ${item.name}.`);
          await onAdded();
        } catch (err) {
          setNote(err instanceof Error ? err.message : 'Could not add the favorite set');
        } finally {
          setBusy(false);
        }
      }}>
        <option value="">{busy ? 'Adding…' : 'Add a saved set…'}</option>
        {items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      {note && <div className="form-text">{note}</div>}
    </div>
  );
}

const EMPTY_DRUG = {
  custom_drug_name: '', custom_generic_name: '',
  dosage: '', dose_morning: '', dose_afternoon: '', dose_evening: '',
  frequency: 'OD', duration: '30 days', instructions: '',
};

export default function Prescribe() {
  const { id } = useParams<{ id: string }>();
  const [visit, setVisit] = useState<VisitDetail | null>(null);
  const [patientAlerts, setPatientAlerts] = useState<{ allergies?: string | null; problem_list?: string | null } | null>(null);
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<DrugSearchResult[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<Brand | null>(null);
  const [isInsulin, setIsInsulin] = useState(false);
  const [warnings, setWarnings] = useState<unknown[]>([]);
  const [morning, setMorning] = useState(true);
  const [afternoon, setAfternoon] = useState(false);
  const [night, setNight] = useState(false);
  const [mealTiming, setMealTiming] = useState('');
  const [bilingualPreview, setBilingualPreview] = useState('');
  const [form, setForm] = useState(EMPTY_DRUG);
  const [addedName, setAddedName] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const [useCustom, setUseCustom] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastRx, setLastRx] = useState<{
    source_visit_id: number | null;
    visit_date: string | null;
    prescriptions: {
      id: number;
      drug_name: string | null;
      custom_drug_name: string | null;
      brand_medication_id?: number | null;
      formatted_dosage: string | null;
      dosage: string | null;
      frequency: string | null;
      duration: string | null;
      timing?: string | null;
      instructions?: string | null;
    }[];
  } | null>(null);
  const [repeating, setRepeating] = useState(false);
  const [copyingId, setCopyingId] = useState<number | null>(null);
  const [currentRx, setCurrentRx] = useState<VisitDetail['prescriptions']>([]);

  const timing = useMemo(() => buildTiming(morning, afternoon, night), [morning, afternoon, night]);

  const instructionDraft = useMemo(
    () => [mealTiming, form.instructions].filter(Boolean).join('. '),
    [mealTiming, form.instructions],
  );

  useEffect(() => {
    const text = instructionDraft.trim();
    if (!text) {
      setBilingualPreview('');
      return;
    }
    const timer = window.setTimeout(() => {
      api.instructionBilingual(text)
        .then(res => setBilingualPreview(res.bilingual || ''))
        .catch(() => setBilingualPreview(''));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [instructionDraft]);

  const applyBrandSelection = useCallback((brand: Brand | null, item?: DrugSearchResult) => {
    if (!brand) {
      setIsInsulin(false);
      return;
    }
    setIsInsulin(brand.is_insulin);
    const dose = suggestedDosage(brand, item);
    if (dose) {
      setForm(f => ({ ...f, dosage: dose }));
    }
  }, []);

  const reloadVisit = useCallback(async () => {
    if (!id) return;
    const v = await api.visit(Number(id));
    setVisit(v);
    setCurrentRx(v.prescriptions || []);
    if (v.patient_id) {
      api.lastPrescriptions(v.patient_id, v.id).then(setLastRx).catch(() => setLastRx(null));
      api.patient(v.patient_id).then(p => setPatientAlerts({ allergies: p.allergies, problem_list: p.problem_list })).catch(() => {});
    }
  }, [id]);

  useEffect(() => {
    reloadVisit().catch(() => {});
  }, [reloadVisit]);

  const repeatLastRx = async () => {
    if (!id || !lastRx?.source_visit_id) return;
    if (!confirm(`Copy ${lastRx.prescriptions.length} medication(s) from the previous visit into this prescription?`)) return;
    setRepeating(true);
    setError('');
    try {
      const res = await api.repeatPrescriptions(Number(id), lastRx.source_visit_id);
      if (res.warnings?.length) setWarnings(res.warnings);
      await reloadVisit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to repeat prescriptions');
    } finally {
      setRepeating(false);
    }
  };

  const copyOnePrior = async (rx: {
    id: number;
    drug_name: string | null;
    custom_drug_name: string | null;
    brand_medication_id?: number | null;
    formatted_dosage: string | null;
    dosage: string | null;
    frequency: string | null;
    duration: string | null;
    timing?: string | null;
    instructions?: string | null;
  }) => {
    if (!id) return;
    setCopyingId(rx.id);
    setError('');
    try {
      const hasBrand = Boolean(rx.brand_medication_id);
      const payload: Record<string, unknown> = {
        brand_id: hasBrand ? rx.brand_medication_id : undefined,
        custom_drug_name: hasBrand ? undefined : (rx.custom_drug_name || rx.drug_name || undefined),
        dosage: rx.dosage || rx.formatted_dosage || undefined,
        frequency: rx.frequency || 'OD',
        duration: rx.duration || '30 days',
        timing: rx.timing || undefined,
        instructions: rx.instructions || undefined,
      };
      const res = await api.addPrescription(Number(id), payload);
      if (res.warnings?.length) setWarnings(res.warnings);
      rememberTyped('drug', rx.drug_name || rx.custom_drug_name || '');
      await reloadVisit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to copy medicine');
    } finally {
      setCopyingId(null);
    }
  };

  useEffect(() => {
    if (search.length >= 2) api.searchDrugs(search).then(setResults);
    else setResults([]);
  }, [search]);

  const selectDrug = async (item: DrugSearchResult) => {
    setUseCustom(false);
    const label = item.display_label || item.generic_name;
    setSearch(label);
    rememberTyped('drug', label);
    setResults([]);
    const brandList = await api.getBrands(item.id);
    setBrands(brandList);
    const brand = item.type === 'brand' && item.brand_id
      ? brandList.find(b => b.id === item.brand_id) || brandList[0] || null
      : brandList[0] || null;
    setSelectedBrand(brand);
    applyBrandSelection(brand, item);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (visit?.status === 'locked') {
      setError('Visit is finalized and locked.');
      return;
    }
    setLoading(true);
    setError('');
    const instructions = [mealTiming, form.instructions].filter(Boolean).join('. ');
    try {
      const payload = useCustom
        ? {
            custom_drug_name: form.custom_drug_name,
            custom_generic_name: form.custom_generic_name,
            dosage: form.dosage,
            dose_morning: form.dose_morning,
            dose_afternoon: form.dose_afternoon,
            dose_evening: form.dose_evening,
            frequency: form.frequency,
            timing: isInsulin ? timing : timing,
            duration: form.duration,
            instructions: instructions || null,
          }
        : {
            brand_id: selectedBrand?.id,
            dosage: form.dosage,
            dose_morning: form.dose_morning,
            dose_afternoon: form.dose_afternoon,
            dose_evening: form.dose_evening,
            frequency: form.frequency,
            timing,
            duration: form.duration,
            instructions: instructions || null,
          };
      const res = await api.addPrescription(Number(id), payload);
      if (res.warnings?.length) setWarnings(res.warnings);
      else setWarnings([]);
      const name = useCustom ? form.custom_drug_name : (selectedBrand?.display_label || selectedBrand?.brand_name || search);
      rememberTyped('drug', name);
      setAddedName(name);
      setSearch('');
      setResults([]);
      setBrands([]);
      setSelectedBrand(null);
      setIsInsulin(false);
      setUseCustom(false);
      setMealTiming('');
      setBilingualPreview('');
      setMorning(true);
      setAfternoon(false);
      setNight(false);
      setForm(current => ({
        ...EMPTY_DRUG,
        frequency: current.frequency,
        duration: current.duration,
      }));
      await reloadVisit();
      searchRef.current?.focus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add prescription');
    } finally {
      setLoading(false);
    }
  };

  if (!visit) return <div>Loading...</div>;

  if (visit.status === 'locked') {
    return (
      <div className="alert alert-warning">
        This visit is finalized and locked. Prescriptions cannot be added.
        <Link to={`/visits/${visit.id}`} className="btn btn-sm btn-outline-secondary ms-2">Back</Link>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Prescribe</h2>
          <p className="page-subtitle">{visit.patient_name}</p>
        </div>
        {lastRx?.source_visit_id && lastRx.prescriptions.length > 0 && (
          <button type="button" className="btn btn-outline-primary" disabled={repeating} onClick={repeatLastRx}>
            <i className="fas fa-copy me-1"></i>
            {repeating ? 'Copying…' : `Repeat last Rx (${lastRx.prescriptions.length})`}
          </button>
        )}
      </div>
      {patientAlerts && (patientAlerts.allergies?.trim() || patientAlerts.problem_list?.trim()) && (
        <div className="alert alert-danger">
          {patientAlerts.allergies?.trim() && <div><strong>Allergies:</strong> {patientAlerts.allergies}</div>}
          {patientAlerts.problem_list?.trim() && <div><strong>Problem list:</strong> {patientAlerts.problem_list}</div>}
        </div>
      )}
      {error && <div className="alert alert-danger">{error}</div>}
      {warnings.length > 0 && (
        <div className="alert alert-warning">
          <strong>Clinical alerts:</strong>
          <ul className="mb-0 mt-1">
            {(warnings as { message?: string; recommendation?: string }[]).map((w, i) => (
              <li key={i}>{w.message || w.recommendation || String(w)}</li>
            ))}
          </ul>
        </div>
      )}
      {lastRx?.source_visit_id && lastRx.prescriptions.length > 0 && (
        <div className="card mb-3 p-3">
          <div className="d-flex justify-content-between align-items-start gap-2 flex-wrap">
            <div>
              <h6 className="mb-1"><i className="fas fa-history me-1"></i>Previous prescription</h6>
              <div className="small text-muted">
                From {lastRx.visit_date ? formatClinicDate(lastRx.visit_date) : 'prior visit'}
              </div>
            </div>
            <button type="button" className="btn btn-sm btn-primary" disabled={repeating} onClick={repeatLastRx}>
              Carry forward all
            </button>
          </div>
          <div className="table-responsive mt-2">
            <table className="table table-sm mb-0 align-middle">
              <tbody>
                {lastRx.prescriptions.map(rx => (
                  <tr key={rx.id}>
                    <td>
                      <strong>{rx.drug_name || rx.custom_drug_name || 'Medication'}</strong>
                      <div className="small text-muted">
                        {[rx.formatted_dosage || rx.dosage, rx.frequency, rx.duration].filter(Boolean).join(' · ')}
                      </div>
                    </td>
                    <td className="text-end text-nowrap">
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        disabled={copyingId === rx.id || repeating}
                        onClick={() => copyOnePrior(rx)}
                      >
                        {copyingId === rx.id ? 'Adding…' : 'Copy'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {currentRx.length > 0 && (
        <div className="card mb-3 p-3">
          <h6 className="mb-2">On this visit</h6>
          <ul className="mb-0 small">
            {currentRx.map(rx => (
              <li key={rx.id}>
                <strong>{rx.drug_name || rx.custom_drug_name || 'Medication'}</strong>
                {' · '}
                {[rx.formatted_dosage || rx.dosage, rx.frequency, rx.duration].filter(Boolean).join(' · ')}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="card p-4">
        <form onSubmit={handleSubmit}>
          <div className="form-check mb-3">
            <input className="form-check-input" type="checkbox" id="custom"
              checked={useCustom} onChange={e => setUseCustom(e.target.checked)} />
            <label className="form-check-label" htmlFor="custom">Manual / custom drug entry</label>
          </div>

          {useCustom ? (
            <div className="row mb-3">
              <div className="col-md-6">
                <label className="form-label">Drug Name *</label>
                <SuggestField
                  field="drug"
                  required
                  value={form.custom_drug_name}
                  onChange={v => setForm({ ...form, custom_drug_name: v })}
                  placeholder="Type to recall prior medicines"
                />
              </div>
              <div className="col-md-6">
                <label className="form-label">Generic Name</label>
                <input className="form-control" value={form.custom_generic_name}
                  onChange={e => setForm({ ...form, custom_generic_name: e.target.value })} />
              </div>
            </div>
          ) : (
            <div className="mb-3 position-relative">
              {id && <FavoriteRx visitId={Number(id)} onAdded={reloadVisit} />}
              <label className="form-label">Search Drug</label>
              <input ref={searchRef} className="form-control" value={search} placeholder="Type 2+ characters..."
                onChange={e => { setSearch(e.target.value); if (e.target.value) setAddedName(''); }} />
              {(results.length > 0 || (search.trim().length >= 1 && recallTyped('drug', search).length > 0)) && (
                <div className="list-group search-results mt-1">
                  {recallTyped('drug', search)
                    .filter(name => !results.some(r =>
                      (r.display_label || r.generic_name || '').toLowerCase() === name.toLowerCase()))
                    .slice(0, 5)
                    .map(name => (
                      <button
                        type="button"
                        key={`recent-${name}`}
                        className="list-group-item list-group-item-action"
                        onClick={() => {
                          setUseCustom(true);
                          setSearch(name);
                          setResults([]);
                          setSelectedBrand(null);
                          setBrands([]);
                          setForm(f => ({ ...f, custom_drug_name: name }));
                          rememberTyped('drug', name);
                        }}
                      >
                        {name}
                        <span className="text-muted small ms-2">recent</span>
                      </button>
                    ))}
                  {results.map((r, i) => (
                    <button type="button" key={i} className="list-group-item list-group-item-action"
                      onClick={() => selectDrug(r)}>
                      {r.display_label || r.generic_name}
                      {r.suggested_dosage && (
                        <span className="text-muted small ms-2">({r.suggested_dosage})</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {selectedBrand && (
                <div className="form-text mt-1">
                  Selected: <strong>{selectedBrand.display_label}</strong>
                  {form.dosage && !isInsulin && (
                    <span className="ms-2 text-success">Dose auto-filled: {form.dosage}</span>
                  )}
                </div>
              )}
              {brands.length > 1 && (
                <div className="mt-2">
                  <label className="form-label">Select Brand</label>
                  <select className="form-select" value={selectedBrand?.id || ''}
                    onChange={e => {
                      const b = brands.find(x => x.id === Number(e.target.value));
                      if (b) {
                        setSelectedBrand(b);
                        applyBrandSelection(b);
                      }
                    }}>
                    {brands.map(b => <option key={b.id} value={b.id}>{b.display_label}</option>)}
                  </select>
                </div>
              )}
            </div>
          )}

          {isInsulin ? (
            <div className="row mb-3">
              {[
                { key: 'dose_morning', label: 'Morning (units)' },
                { key: 'dose_afternoon', label: 'Afternoon (units)' },
                { key: 'dose_evening', label: 'Night (units)' },
              ].map(f => (
                <div className="col-md-4" key={f.key}>
                  <label className="form-label">{f.label}</label>
                  <input className="form-control" value={form[f.key as keyof typeof form]}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })} />
                </div>
              ))}
            </div>
          ) : (
            <div className="row mb-3">
              <div className="col-md-4">
                <label className="form-label">Dosage</label>
                <input className="form-control" value={form.dosage}
                  onChange={e => setForm({ ...form, dosage: e.target.value })} />
              </div>
              <div className="col-md-4">
                <label className="form-label">Frequency</label>
                <select className="form-select" value={form.frequency}
                  onChange={e => setForm({ ...form, frequency: e.target.value })}>
                  {FREQUENCIES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                </select>
              </div>
              <div className="col-md-4">
                <label className="form-label">Meal timing (optional)</label>
                <select className="form-select" value={mealTiming} onChange={e => setMealTiming(e.target.value)}>
                  {MEAL_TIMING.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
            </div>
          )}

          <div className="card bg-light mb-3 p-3">
            <label className="form-label fw-semibold">Timing — Morning / Afternoon / Night</label>
            <div className="d-flex flex-wrap gap-4 mb-2">
              <div className="form-check">
                <input className="form-check-input" type="checkbox" id="tm"
                  checked={morning} onChange={e => setMorning(e.target.checked)} />
                <label className="form-check-label" htmlFor="tm">Morning</label>
              </div>
              <div className="form-check">
                <input className="form-check-input" type="checkbox" id="ta"
                  checked={afternoon} onChange={e => setAfternoon(e.target.checked)} />
                <label className="form-check-label" htmlFor="ta">Afternoon</label>
              </div>
              <div className="form-check">
                <input className="form-check-input" type="checkbox" id="tn"
                  checked={night} onChange={e => setNight(e.target.checked)} />
                <label className="form-check-label" htmlFor="tn">Night</label>
              </div>
            </div>
            <div className="small">
              Timing code: <strong className="fs-5">{timing}</strong>
              <span className="text-muted ms-2">
                ({morning ? 'AM' : '—'} / {afternoon ? 'PM' : '—'} / {night ? 'Night' : '—'})
              </span>
            </div>
          </div>

          <div className="row mb-3">
            <div className="col-md-4">
              <label className="form-label">Duration *</label>
              <input className="form-control" required value={form.duration}
                onChange={e => setForm({ ...form, duration: e.target.value })} />
            </div>
            <div className="col-md-8">
              <label className="form-label">Special Instructions</label>
              <input className="form-control" value={form.instructions}
                onChange={e => setForm({ ...form, instructions: e.target.value })} />
              {bilingualPreview && (
                <div className="form-text mt-1" style={{ fontFamily: 'Noto Sans Kannada, sans-serif' }}>
                  <span className="text-muted">Kannada (auto): </span>
                  {bilingualPreview}
                </div>
              )}
            </div>
          </div>

          {addedName && (
            <div className="alert alert-success py-2">
              Added <strong>{addedName}</strong>. Search the next medicine, or choose Done when the list is complete.
            </div>
          )}
          <button type="submit" className="btn btn-primary me-2" disabled={loading}>
            {loading ? 'Adding...' : 'Add Prescription'}
          </button>
          <Link to={`/visits/${id}`} className="btn btn-outline-secondary">Done</Link>
        </form>
      </div>
    </div>
  );
}
