import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, Brand, DrugSearchResult, VisitDetail } from '../api/client';

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

export default function Prescribe() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [visit, setVisit] = useState<VisitDetail | null>(null);
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
  const [form, setForm] = useState({
    custom_drug_name: '', custom_generic_name: '',
    dosage: '', dose_morning: '', dose_afternoon: '', dose_evening: '',
    frequency: 'OD', duration: '30 days', instructions: '',
  });
  const [useCustom, setUseCustom] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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

  useEffect(() => {
    if (id) api.visit(Number(id)).then(setVisit);
  }, [id]);

  useEffect(() => {
    if (search.length >= 2) api.searchDrugs(search).then(setResults);
    else setResults([]);
  }, [search]);

  const selectDrug = async (item: DrugSearchResult) => {
    setUseCustom(false);
    setSearch(item.display_label || item.generic_name);
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
      navigate(`/visits/${id}`);
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
      <h2 className="mb-4">Prescribe — {visit.patient_name}</h2>
      {error && <div className="alert alert-danger">{error}</div>}
      {warnings.length > 0 && (
        <div className="alert alert-warning">
          <strong>Clinical alerts:</strong>
          <ul className="mb-0 mt-1">
            {(warnings as { message?: string }[]).map((w, i) => (
              <li key={i}>{w.message || String(w)}</li>
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
                <input className="form-control" required value={form.custom_drug_name}
                  onChange={e => setForm({ ...form, custom_drug_name: e.target.value })} />
              </div>
              <div className="col-md-6">
                <label className="form-label">Generic Name</label>
                <input className="form-control" value={form.custom_generic_name}
                  onChange={e => setForm({ ...form, custom_generic_name: e.target.value })} />
              </div>
            </div>
          ) : (
            <div className="mb-3 position-relative">
              <label className="form-label">Search Drug</label>
              <input className="form-control" value={search} placeholder="Type 2+ characters..."
                onChange={e => setSearch(e.target.value)} />
              {results.length > 0 && (
                <div className="list-group search-results mt-1">
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

          <button type="submit" className="btn btn-primary me-2" disabled={loading}>
            {loading ? 'Adding...' : 'Add Prescription'}
          </button>
          <Link to={`/visits/${id}`} className="btn btn-outline-secondary">Cancel</Link>
        </form>
      </div>
    </div>
  );
}
