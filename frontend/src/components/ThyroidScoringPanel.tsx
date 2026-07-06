import { useMemo } from 'react';

export const WHO_GOITRE_OPTIONS = [
  { grade: '0', title: 'WHO Grade 0', detail: 'No goitre palpable or visible' },
  { grade: '1', title: 'WHO Grade 1', detail: 'Palpable but not visible with neck in normal position' },
  { grade: '2', title: 'WHO Grade 2', detail: 'Palpable and visible with neck in normal position' },
] as const;

export const CAS_ITEMS = [
  { key: 'cas_spontaneous_pain', label: 'Spontaneous retrobulbar pain' },
  { key: 'cas_gaze_pain', label: 'Pain on attempted upward/downward gaze' },
  { key: 'cas_eyelid_erythema', label: 'Eyelid erythema' },
  { key: 'cas_eyelid_swelling', label: 'Eyelid swelling' },
  { key: 'cas_conjunctival_redness', label: 'Conjunctival redness' },
  { key: 'cas_chemosis', label: 'Chemosis' },
  { key: 'cas_caruncle_inflammation', label: 'Caruncle/plica inflammation' },
] as const;

export const TED_SEVERITY_OPTIONS = [
  { grade: 'N', title: 'No TED (N)', detail: 'No signs or symptoms of thyroid eye disease' },
  { grade: 'mild', title: 'Mild', detail: 'Minor lid retraction, mild soft tissue changes' },
  { grade: 'moderate_severe', title: 'Moderate-to-severe', detail: 'Significant lid retraction, proptosis, soft tissue disease, or diplopia' },
  { grade: 'sight_threatening', title: 'Sight-threatening', detail: 'Dysthyroid optic neuropathy or corneal breakdown' },
] as const;

function casTotal(data: Record<string, string>) {
  return CAS_ITEMS.reduce((sum, item) => sum + (data[item.key] === '1' ? 1 : 0), 0);
}

function casInterpretation(total: number) {
  const active = total >= 3;
  return {
    active,
    label: active ? 'Active thyroid eye disease (≥3)' : 'Inactive thyroid eye disease (<3)',
  };
}

type Props = {
  data: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
};

export default function ThyroidScoringPanel({ data, onChange }: Props) {
  const casScore = useMemo(() => casTotal(data), [data]);
  const casResult = useMemo(() => casInterpretation(casScore), [casScore]);
  const whoGrade = data.who_goitre_grade || '';
  const tedSeverity = data.ted_severity || '';

  const setWhoGoitre = (grade: string) => {
    const opt = WHO_GOITRE_OPTIONS.find(o => o.grade === grade);
    onChange({
      ...data,
      who_goitre_grade: grade,
      who_goitre_interpretation: opt?.detail || '',
    });
  };

  const toggleCas = (key: string) => {
    const next = { ...data, [key]: data[key] === '1' ? '0' : '1' };
    const total = casTotal(next);
    const interp = casInterpretation(total);
    onChange({
      ...next,
      cas_total: String(total),
      cas_interpretation: interp.label,
    });
  };

  const setTedSeverity = (grade: string) => {
    const opt = TED_SEVERITY_OPTIONS.find(o => o.grade === grade);
    onChange({
      ...data,
      ted_severity: grade,
      ted_severity_label: opt?.title || '',
    });
  };

  const setProptosis = (value: string) => {
    onChange({ ...data, proptosis: value });
  };

  return (
    <div className="card bg-light p-3 mb-3">
      <h6 className="mb-2">
        <i className="fas fa-notes-medical me-1" />
        Thyroid Clinical Assessment
      </h6>
      <p className="small text-muted mb-3">
        WHO goitre classification, Clinical Activity Score (CAS) for Graves&apos; ophthalmopathy, and EUGOGO severity grading.
      </p>

      <div className="small fw-semibold mb-2">WHO goitre classification</div>
      <div className="row g-2 mb-3">
        {WHO_GOITRE_OPTIONS.map(opt => (
          <div className="col-md-4" key={opt.grade}>
            <button
              type="button"
              className={`card p-3 w-100 text-start border ${whoGrade === opt.grade ? 'border-primary bg-white shadow-sm' : 'bg-white'}`}
              onClick={() => setWhoGoitre(opt.grade)}
            >
              <div className="small fw-semibold">{opt.title}</div>
              <div className="small text-muted">{opt.detail}</div>
            </button>
          </div>
        ))}
      </div>

      <hr className="my-3" />

      <div className="small fw-semibold mb-2">Clinical Activity Score (CAS) — Graves&apos; ophthalmopathy</div>
      <p className="small text-muted mb-2">Each item scores 1 if present. CAS ≥3 indicates active disease (EUGOGO).</p>
      <div className="row g-2 mb-2">
        {CAS_ITEMS.map(item => (
          <div className="col-md-6" key={item.key}>
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                id={`cas-${item.key}`}
                checked={data[item.key] === '1'}
                onChange={() => toggleCas(item.key)}
              />
              <label className="form-check-label small" htmlFor={`cas-${item.key}`}>{item.label}</label>
            </div>
          </div>
        ))}
      </div>
      <div className={`alert py-2 small mb-3 ${casResult.active ? 'alert-warning' : 'alert-success'}`}>
        <strong>CAS total: {casScore}/7</strong> — {casResult.label}
      </div>

      <hr className="my-3" />

      <div className="small fw-semibold mb-2">Thyroid eye disease severity (EUGOGO)</div>
      <div className="row g-2 mb-2">
        {TED_SEVERITY_OPTIONS.map(opt => (
          <div className="col-md-6 col-lg-3" key={opt.grade}>
            <button
              type="button"
              className={`card p-2 w-100 text-start border ${tedSeverity === opt.grade ? 'border-primary bg-white shadow-sm' : 'bg-white'}`}
              onClick={() => setTedSeverity(opt.grade)}
            >
              <div className="small fw-semibold">{opt.title}</div>
              <div className="small text-muted">{opt.detail}</div>
            </button>
          </div>
        ))}
      </div>

      <div className="row g-2 align-items-end">
        <div className="col-md-4">
          <label className="form-label small mb-1">Proptosis (mm)</label>
          <input
            type="number"
            className="form-control form-control-sm"
            placeholder="e.g. 18"
            min="0"
            step="0.5"
            value={data.proptosis || ''}
            onChange={e => setProptosis(e.target.value)}
          />
          <div className="form-text">Hertel exophthalmometry — document if measured</div>
        </div>
      </div>

      {tedSeverity && (
        <div className="alert alert-info mt-2 mb-0 py-2 small">
          TED severity: {TED_SEVERITY_OPTIONS.find(o => o.grade === tedSeverity)?.title}
          {data.proptosis ? ` · Proptosis ${data.proptosis} mm` : ''}
        </div>
      )}
    </div>
  );
}
