import { useMemo } from 'react';

export const FG_SITES = [
  { key: 'fg_upper_lip', label: 'Upper lip', zone: 'face' },
  { key: 'fg_chin', label: 'Chin', zone: 'face' },
  { key: 'fg_chest', label: 'Chest', zone: 'front' },
  { key: 'fg_upper_abdomen', label: 'Upper abdomen', zone: 'front' },
  { key: 'fg_lower_abdomen', label: 'Lower abdomen', zone: 'front' },
  { key: 'fg_upper_back', label: 'Upper back', zone: 'back' },
  { key: 'fg_lower_back', label: 'Lower back', zone: 'back' },
  { key: 'fg_thighs', label: 'Thighs', zone: 'limbs' },
  { key: 'fg_upper_arms', label: 'Upper arms', zone: 'limbs' },
] as const;

const FG_REFERENCE_IMAGE = '/scoring/ferriman-gallwey-reference.png';
const LUDWIG_REFERENCE_IMAGE = '/scoring/ludwig-reference.png';

const LUDWIG_OPTIONS = [
  {
    grade: 'I',
    title: 'Ludwig Grade I',
    detail: 'Thinning on crown; frontal hairline preserved',
  },
  {
    grade: 'II',
    title: 'Ludwig Grade II',
    detail: 'Pronounced rarefaction on crown; frontal hairline preserved',
  },
  {
    grade: 'III',
    title: 'Ludwig Grade III',
    detail: 'Full baldness on crown; frontal hairline preserved',
  },
];

function fgTotal(data: Record<string, string>) {
  return FG_SITES.reduce((sum, s) => sum + (Number(data[s.key]) || 0), 0);
}

function fgInterpretation(total: number) {
  const threshold = 6;
  if (total < threshold) return { severity: 'Normal', meets: false };
  if (total < 15) return { severity: 'Mild hirsutism', meets: true };
  if (total < 25) return { severity: 'Moderate hirsutism', meets: true };
  return { severity: 'Severe hirsutism', meets: true };
}

type Props = {
  data: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
};

export default function PcosScoringPanel({ data, onChange }: Props) {
  const total = useMemo(() => fgTotal(data), [data]);
  const fgResult = useMemo(() => fgInterpretation(total), [total]);
  const ludwig = data.ludwig_grade || '';

  const setSite = (key: string, value: string) => {
    const next = { ...data, [key]: value };
    const newTotal = fgTotal(next);
    const interp = fgInterpretation(newTotal);
    onChange({
      ...next,
      ferriman_gallwey_total: String(newTotal),
      fg_interpretation: interp.severity,
    });
  };

  const setLudwig = (grade: string) => {
    onChange({ ...data, ludwig_grade: grade });
  };

  return (
    <div className="card bg-light p-3 mb-3">
      <h6 className="mb-2">
        <i className="fas fa-female me-1" />
        PCOS Clinical Scoring
      </h6>
      <p className="small text-muted mb-3">
        Modified Ferriman-Gallwey (9 sites, 0–4 each) and Ludwig androgenic alopecia grading.
        Score each site using the reference chart below (0 = no terminal hair). Threshold ≥6 for South Asian women.
      </p>

      <div className="card p-2 mb-3 bg-white">
        <div className="small fw-semibold mb-2 text-center">Modified Ferriman-Gallwey reference chart</div>
        <a href={FG_REFERENCE_IMAGE} target="_blank" rel="noopener noreferrer" title="Open full-size reference chart">
          <img
            src={FG_REFERENCE_IMAGE}
            alt="Modified Ferriman-Gallwey scoring reference — 9 body areas with grades 1 to 4 for hirsutism assessment"
            className="img-fluid rounded border w-100"
            style={{ maxHeight: 520, objectFit: 'contain' }}
          />
        </a>
        <div className="small text-muted text-center mt-2">
          Upper lip · Chin · Chest · Upper abdomen · Lower abdomen · Upper arms · Thighs · Upper back · Lower back
        </div>
      </div>

      <div className="row g-2 mb-2">
        {FG_SITES.map(site => (
          <div className="col-md-4 col-6" key={site.key}>
            <label className="form-label small mb-1">{site.label}</label>
            <div className="btn-group btn-group-sm w-100" role="group">
              {[0, 1, 2, 3, 4].map(score => (
                <button
                  key={score}
                  type="button"
                  className={`btn ${Number(data[site.key]) === score ? 'btn-primary' : 'btn-outline-secondary'}`}
                  onClick={() => setSite(site.key, String(score))}
                  title={`${site.label}: score ${score}`}
                >
                  {score}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className={`alert mb-3 py-2 small ${fgResult.meets ? 'alert-warning' : 'alert-success'}`}>
        <strong>Modified FG total: {total}/36</strong> — {fgResult.severity}
        {fgResult.meets && ' · Meets clinical hyperandrogenism criterion (hirsutism)'}
      </div>

      <hr className="my-3" />

      <div className="small fw-semibold mb-2">Ludwig pattern hair loss (androgenic alopecia)</div>
      <p className="small text-muted mb-2">
        Compare the patient&apos;s crown thinning to the reference chart and select the matching grade.
      </p>

      <div className="card p-2 mb-3 bg-white">
        <div className="small fw-semibold mb-2 text-center">Ludwig scale reference chart</div>
        <a href={LUDWIG_REFERENCE_IMAGE} target="_blank" rel="noopener noreferrer" title="Open full-size Ludwig reference chart">
          <img
            src={LUDWIG_REFERENCE_IMAGE}
            alt="Ludwig scale reference — Grade 1 mild crown thinning, Grade 2 moderate, Grade 3 severe androgenic alopecia"
            className="img-fluid rounded border w-100"
            style={{ maxHeight: 280, objectFit: 'contain' }}
          />
        </a>
        <div className="small text-muted text-center mt-2">
          Grade 1 (mild) · Grade 2 (moderate) · Grade 3 (severe)
        </div>
      </div>

      <div className="row g-2">
        {LUDWIG_OPTIONS.map(opt => (
          <div className="col-md-4" key={opt.grade}>
            <button
              type="button"
              className={`card p-3 w-100 text-start border ${ludwig === opt.grade ? 'border-primary bg-white shadow-sm' : 'bg-white'}`}
              onClick={() => setLudwig(opt.grade)}
            >
              <div className="small fw-semibold">{opt.title}</div>
              <div className="small text-muted">{opt.detail}</div>
            </button>
          </div>
        ))}
      </div>
      {ludwig && (
        <div className="alert alert-info mt-2 mb-0 py-2 small">
          Selected: Ludwig Grade {ludwig} — {LUDWIG_OPTIONS.find(o => o.grade === ludwig)?.detail}
        </div>
      )}
    </div>
  );
}
