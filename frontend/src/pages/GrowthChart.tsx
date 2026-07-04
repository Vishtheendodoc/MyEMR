import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ComposedChart, Line, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { api, PatientDetail } from '../api/client';

type CurvePoint = Record<string, number>;
type HistoryPoint = {
  date: string;
  age_years: number;
  age_months: number;
  height_cm: number;
  weight_kg?: number | null;
  bmi?: number | null;
  chart: 'infant' | 'child';
  z_score?: number | null;
  sd_score?: number | null;
  median_cm?: number;
  sd_cm?: number;
  out_of_range?: boolean;
  reference_note?: string;
};
type ChartDef = {
  label: string;
  x_label: string;
  x_key: string;
  y_label: string;
  reference: string;
  x_min?: number;
  x_max?: number;
  curves: CurvePoint[];
};
type GrowthData = {
  patient_age_years: number;
  patient_age_months: number;
  sex: string;
  is_pediatric: boolean;
  within_cdc_range?: boolean;
  cdc_age_max_years?: number;
  mid_parental_height: number | null;
  active_chart: 'infant' | 'child';
  charts: { infant: ChartDef; child: ChartDef };
  history: HistoryPoint[];
  latest: HistoryPoint | null;
};

function chartYDomain(curves: CurvePoint[], heights: number[]): [number, number] {
  const ys = curves.flatMap(c => [c.sd_m2, c.sd_p2]);
  const all = [...ys, ...heights].filter(v => typeof v === 'number' && !Number.isNaN(v));
  if (!all.length) return [50, 190];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const pad = Math.max(5, (max - min) * 0.06);
  return [Math.floor(min - pad), Math.ceil(max + pad)];
}

function round1(n: number) {
  return Math.round(n * 10) / 10;
}

/** Interpolate CDC reference lines at any x (age) along the chart. */
function interpCurveAt(curves: CurvePoint[], xKey: string, age: number): CurvePoint {
  if (!curves.length) return { [xKey]: age };
  const sorted = [...curves].sort((a, b) => (a[xKey] as number) - (b[xKey] as number));
  const x0 = sorted[0][xKey] as number;
  const xLast = sorted[sorted.length - 1][xKey] as number;
  const clamped = Math.max(x0, Math.min(xLast, age));

  if (clamped <= x0) return sorted[0];
  if (clamped >= xLast) return sorted[sorted.length - 1];

  for (let i = 0; i < sorted.length - 1; i++) {
    const a0 = sorted[i][xKey] as number;
    const a1 = sorted[i + 1][xKey] as number;
    if (clamped >= a0 && clamped <= a1) {
      if (a1 === a0) return sorted[i];
      const t = (clamped - a0) / (a1 - a0);
      const lerp = (k: string) => round1(sorted[i][k] + t * (sorted[i + 1][k] - sorted[i][k]));
      return {
        [xKey]: round1(clamped),
        sd_m2: lerp('sd_m2'),
        sd_m1: lerp('sd_m1'),
        sd_0: lerp('sd_0'),
        sd_p1: lerp('sd_p1'),
        sd_p2: lerp('sd_p2'),
      };
    }
  }
  return sorted[sorted.length - 1];
}

type PatientPlot = {
  height_cm: number;
  actual_age?: string;
  out_of_range?: boolean;
  [key: string]: unknown;
};

function GrowthChartTooltip({
  active,
  label,
  curves,
  xKey,
  xUnit,
  patientPoints,
}: {
  active?: boolean;
  label?: string | number;
  curves: CurvePoint[];
  xKey: string;
  xUnit: string;
  patientPoints: PatientPlot[];
}) {
  if (!active || label == null || label === '') return null;

  const age = Number(label);
  if (Number.isNaN(age)) return null;

  const ref = interpCurveAt(curves, xKey, age);
  const nearbyPatients = patientPoints.filter(p => {
    const px = p[xKey] as number;
    return Math.abs(px - age) < 0.6;
  });

  const rows: { color: string; name: string; value: number }[] = [
    { color: '#dee2e6', name: '-2 SD', value: ref.sd_m2 as number },
    { color: '#adb5bd', name: '-1 SD', value: ref.sd_m1 as number },
    { color: '#0d6efd', name: 'Median', value: ref.sd_0 as number },
    { color: '#adb5bd', name: '+1 SD', value: ref.sd_p1 as number },
    { color: '#dee2e6', name: '+2 SD', value: ref.sd_p2 as number },
  ];

  return (
    <div className="bg-white border rounded shadow-sm p-2 small" style={{ minWidth: 160 }}>
      <div className="fw-semibold mb-1">Age {round1(age)} {xUnit}</div>
      {rows.map(r => (
        <div key={r.name} className="d-flex justify-content-between gap-3">
          <span style={{ color: r.color === '#0d6efd' ? r.color : '#666' }}>
            {r.name === 'Median' ? <strong>{r.name}</strong> : r.name}:
          </span>
          <span>{r.value} cm</span>
        </div>
      ))}
      {nearbyPatients.map((p, i) => (
        <div key={i} className="d-flex justify-content-between gap-3 mt-1 pt-1 border-top">
          <span className="text-danger fw-semibold">Patient{p.out_of_range && p.actual_age ? '*' : ''}:</span>
          <span>{p.height_cm} cm</span>
        </div>
      ))}
      {nearbyPatients.some(p => p.out_of_range && p.actual_age) && (
        <div className="text-muted mt-1" style={{ fontSize: '0.75rem' }}>
          * plotted at chart edge (actual {nearbyPatients.find(p => p.actual_age)?.actual_age})
        </div>
      )}
    </div>
  );
}

export default function GrowthChart() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [data, setData] = useState<GrowthData | null>(null);
  const [chartTab, setChartTab] = useState<'infant' | 'child'>('child');
  const printRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    api.patient(pid).then(setPatient);
    api.growthChart(pid).then(d => {
      const g = d as GrowthData;
      setData(g);
      setChartTab(g.active_chart || 'child');
    });
  }, [id]);

  const chartDef = data?.charts[chartTab];
  const xKey = chartDef?.x_key || 'age_years';

  const patientPoints = useMemo(() => {
    if (!data || !chartDef) return [];
    const xMin = chartDef.x_min ?? (chartTab === 'infant' ? 0 : 2);
    const xMax = chartDef.x_max ?? (chartTab === 'infant' ? 24 : 20);
    return data.history
      .filter(h => h.chart === chartTab && h.height_cm)
      .map(h => {
        const rawX = chartTab === 'infant' ? h.age_months : h.age_years;
        const plotX = chartTab === 'infant'
          ? Math.min(Math.max(rawX, xMin), xMax)
          : Math.min(Math.max(rawX, xMin), xMax);
        return {
          [xKey]: plotX,
          height_cm: h.height_cm,
          date: h.date,
          z_score: h.z_score,
          out_of_range: h.out_of_range || rawX < xMin || rawX > xMax,
          actual_age: chartTab === 'infant'
            ? `${h.age_months.toFixed(1)} mo`
            : `${h.age_years.toFixed(1)} yr`,
        };
      });
  }, [data, chartTab, chartDef, xKey]);

  const xDomain = useMemo((): [number, number] => {
    if (!chartDef) return chartTab === 'infant' ? [0, 24] : [2, 20];
    return [chartDef.x_min ?? (chartTab === 'infant' ? 0 : 2), chartDef.x_max ?? (chartTab === 'infant' ? 24 : 20)];
  }, [chartDef, chartTab]);

  const yDomain = useMemo(
    () => chartYDomain(chartDef?.curves ?? [], patientPoints.map(p => p.height_cm)),
    [chartDef, patientPoints],
  );

  const hasOutOfRange = data?.history.some(h => h.out_of_range) ?? false;

  const handlePrint = () => window.print();

  if (!patient || !data || !chartDef) return <div>Loading...</div>;

  const mph = chartTab === 'child' ? data.mid_parental_height : null;

  return (
    <div>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #growth-print-area, #growth-print-area * { visibility: visible; }
          #growth-print-area { position: absolute; left: 0; top: 0; width: 100%; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="d-flex justify-content-between mb-4 no-print">
        <h2>Growth Chart — {patient.name}</h2>
        <div className="d-flex gap-2">
          <button type="button" className="btn btn-outline-primary" onClick={handlePrint}>
            <i className="fas fa-print me-1"></i>Print Chart
          </button>
          <Link to={`/patients/${patient.id}`} className="btn btn-outline-secondary">Back</Link>
        </div>
      </div>

      <div id="growth-print-area" ref={printRef}>
        <div className="mb-3">
          <p className="mb-1">
            <strong>{patient.name}</strong> · {patient.sex} · Age {data.patient_age_years} years
            ({data.patient_age_months} months)
          </p>
          {data.latest && (
            <p className="mb-0 text-muted small">
              Latest: {data.latest.height_cm} cm — SD score (Z): {data.latest.z_score ?? 'N/A'}
            </p>
          )}
        </div>

        {hasOutOfRange && (
          <div className="alert alert-warning py-2 small no-print">
            <i className="fas fa-exclamation-triangle me-1"></i>
            Patient age ({data.patient_age_years} years) is outside the CDC 2–20 year chart range.
            The point is shown at the nearest chart edge; Z-score uses age {data.cdc_age_max_years ?? 20} year CDC norms.
          </div>
        )}

        <div className="btn-group mb-3 no-print" role="group">
          <button type="button" className={`btn btn-sm ${chartTab === 'infant' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setChartTab('infant')}>
            0–2 years (CDC)
          </button>
          <button type="button" className={`btn btn-sm ${chartTab === 'child' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setChartTab('child')}>
            2–20 years (CDC)
          </button>
        </div>

        <div className="card mb-4 p-3">
          <h5 className="mb-1">{chartDef.label}</h5>
          <p className="text-muted small mb-3">
            {chartDef.reference} reference · Lines show −2SD, −1SD, median, +1SD, +2SD
            {mph ? ` · Mid-parental height: ${mph} cm` : ''}
          </p>
          <ResponsiveContainer width="100%" height={360}>
            <ComposedChart data={chartDef.curves} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey={xKey}
                type="number"
                domain={xDomain}
                allowDataOverflow
                label={{ value: chartDef.x_label, position: 'insideBottom', offset: -5 }}
              />
              <YAxis
                label={{ value: chartDef.y_label, angle: -90, position: 'insideLeft' }}
                domain={yDomain}
                allowDataOverflow
              />
              <Tooltip
                cursor={{ stroke: '#adb5bd', strokeDasharray: '4 4' }}
                content={props => (
                  <GrowthChartTooltip
                    {...props}
                    curves={chartDef.curves}
                    xKey={xKey}
                    xUnit={chartTab === 'infant' ? 'mo' : 'yr'}
                    patientPoints={patientPoints}
                  />
                )}
              />
              <Legend />
              <Line type="monotone" dataKey="sd_m2" stroke="#dee2e6" name="-2 SD" dot={false} strokeWidth={1} isAnimationActive={false} />
              <Line type="monotone" dataKey="sd_m1" stroke="#adb5bd" name="-1 SD" dot={false} strokeWidth={1} isAnimationActive={false} />
              <Line type="monotone" dataKey="sd_0" stroke="#0d6efd" name="Median" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="sd_p1" stroke="#adb5bd" name="+1 SD" dot={false} strokeWidth={1} isAnimationActive={false} />
              <Line type="monotone" dataKey="sd_p2" stroke="#dee2e6" name="+2 SD" dot={false} strokeWidth={1} isAnimationActive={false} />
              {mph != null && (
                <ReferenceLine y={mph} stroke="#198754" strokeDasharray="6 4"
                  label={{ value: `MPH ${mph} cm`, position: 'right', fill: '#198754' }} />
              )}
              <Scatter data={patientPoints} dataKey="height_cm" fill="#dc3545" name="Patient" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {data.history.length > 0 && (
          <div className="card p-3">
            <h5>Measurements & SD Scores</h5>
            <table className="table table-sm mb-0">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Age</th>
                  <th>Chart</th>
                  <th>Height (cm)</th>
                  <th>Weight (kg)</th>
                  <th>Median (cm)</th>
                  <th>SD (cm)</th>
                  <th>SD Score (Z)</th>
                </tr>
              </thead>
              <tbody>
                {data.history.map((h, i) => (
                  <tr key={i}>
                    <td>{h.date}</td>
                    <td>{h.age_months.toFixed(1)} mo / {h.age_years.toFixed(1)} yr</td>
                    <td>{h.chart === 'infant' ? '0–2 yr' : '2–20 yr'}</td>
                    <td>{h.height_cm}</td>
                    <td>{h.weight_kg ?? '-'}</td>
                    <td>{h.median_cm ?? '-'}</td>
                    <td>{h.sd_cm ?? '-'}</td>
                    <td>
                      <strong>{h.sd_score ?? h.z_score ?? '-'}</strong>
                      {h.reference_note && (
                        <div className="text-muted small">{h.reference_note}</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
