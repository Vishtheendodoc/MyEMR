import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import {
  api,
  ImagingResult,
  LabResult,
  Prescription,
  VisitDetail,
  VisitSummary,
} from '../api/client';
import { clinicDayKey, formatClinicDate } from '../utils/clinicTime';

type Tab = 'visits' | 'labs' | 'imaging' | 'rx';

type CopyTarget = {
  diagnosis?: string;
  chief_complaints?: string;
  history?: string;
  examination?: string;
  investigation?: string;
  comorbidities?: string;
};

type Props = {
  patientId: number;
  patientName: string;
  visits: VisitSummary[];
  excludeVisitId?: number | null;
  open: boolean;
  onClose: () => void;
  onCopyToForm?: (fields: CopyTarget) => void;
};

const WIDTH_KEY = 'endoemr-old-reports-width';
const WIDTH_MIN = 360;
const WIDTH_MAX_RATIO = 0.96;

function formatDate(iso: string) {
  return formatClinicDate(iso);
}

function dateKey(iso: string) {
  return clinicDayKey(iso);
}

function drugLabel(rx: Prescription) {
  return rx.drug_name || rx.custom_drug_name || rx.generic_name || rx.custom_generic_name || 'Medication';
}

function parseNumber(value: string | null | undefined): number | null {
  if (value == null || value === '') return null;
  const m = String(value).replace(/,/g, '').match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : null;
}

/** Returns 'high' | 'low' | null when reference looks like "0.6-1.2" or "4 – 23". */
function flagAgainstRef(value: string | null | undefined, reference: string | null | undefined): 'high' | 'low' | null {
  const n = parseNumber(value);
  if (n == null || !reference) return null;
  const m = reference.replace(/,/g, '').match(/(-?\d+(\.\d+)?)\s*[-–—to]+\s*(-?\d+(\.\d+)?)/i);
  if (!m) return null;
  const low = Number(m[1]);
  const high = Number(m[3]);
  if (Number.isNaN(low) || Number.isNaN(high)) return null;
  if (n < low) return 'low';
  if (n > high) return 'high';
  return null;
}

function buildLabMatrix(labs: LabResult[]) {
  const dates = Array.from(new Set(labs.map(l => dateKey(l.result_date)).filter(Boolean)))
    .sort((a, b) => a.localeCompare(b));
  const byTest = new Map<string, {
    test_name: string;
    unit: string | null;
    reference_range: string | null;
    cells: Record<string, { value: string; flag: 'high' | 'low' | null }>;
  }>();
  labs.forEach(lab => {
    const key = lab.test_name.trim().toLowerCase();
    if (!key) return;
    let row = byTest.get(key);
    if (!row) {
      row = {
        test_name: lab.test_name,
        unit: lab.unit,
        reference_range: lab.reference_range,
        cells: {},
      };
      byTest.set(key, row);
    }
    if (!row.unit && lab.unit) row.unit = lab.unit;
    if (!row.reference_range && lab.reference_range) row.reference_range = lab.reference_range;
    const dk = dateKey(lab.result_date);
    const flag = flagAgainstRef(lab.value, lab.reference_range || row.reference_range);
    // Prefer later entry same day (higher id wins via append order)
    row.cells[dk] = { value: lab.value, flag };
  });
  const rows = Array.from(byTest.values()).sort((a, b) => a.test_name.localeCompare(b.test_name));
  return { dates, rows };
}

function loadSavedWidth() {
  try {
    const n = Number(localStorage.getItem(WIDTH_KEY));
    if (n >= WIDTH_MIN) return n;
  } catch { /* ignore */ }
  return Math.min(640, typeof window !== 'undefined' ? Math.round(window.innerWidth * 0.55) : 640);
}

export default function OldReportsPanel({
  patientId,
  patientName,
  visits,
  excludeVisitId,
  open,
  onClose,
  onCopyToForm,
}: Props) {
  const priorVisits = useMemo(
    () => visits.filter(v => v.id !== excludeVisitId),
    [visits, excludeVisitId],
  );

  const [tab, setTab] = useState<Tab>('visits');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<VisitDetail | null>(null);
  const [loadingVisit, setLoadingVisit] = useState(false);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [imaging, setImaging] = useState<ImagingResult[]>([]);
  const [metaLoaded, setMetaLoaded] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [copied, setCopied] = useState('');
  const [error, setError] = useState('');
  const [drawerWidth, setDrawerWidth] = useState(loadSavedWidth);
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);

  const labMatrix = useMemo(() => buildLabMatrix(labs), [labs]);

  const clampWidth = useCallback((w: number) => {
    const max = Math.round(window.innerWidth * WIDTH_MAX_RATIO);
    return Math.max(WIDTH_MIN, Math.min(max, Math.round(w)));
  }, []);

  const setWidthPersist = useCallback((w: number) => {
    const next = clampWidth(w);
    setDrawerWidth(next);
    try { localStorage.setItem(WIDTH_KEY, String(next)); } catch { /* ignore */ }
  }, [clampWidth]);

  const onResizeStart = (e: ReactMouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragRef.current = { startX: e.clientX, startW: drawerWidth };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      // Dragging the left edge: move left → wider
      const delta = dragRef.current.startX - ev.clientX;
      setDrawerWidth(clampWidth(dragRef.current.startW + delta));
    };
    const onUp = () => {
      if (dragRef.current) {
        try { localStorage.setItem(WIDTH_KEY, String(drawerWidth)); } catch { /* ignore */ }
      }
      // Persist latest from state via functional update
      setDrawerWidth(w => {
        try { localStorage.setItem(WIDTH_KEY, String(w)); } catch { /* ignore */ }
        return w;
      });
      dragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  useEffect(() => {
    if (!open) return;
    if (priorVisits.length && selectedId == null) {
      setSelectedId(priorVisits[0].id);
    }
  }, [open, priorVisits, selectedId]);

  useEffect(() => {
    if (!open || metaLoaded) return;
    Promise.all([api.labs(patientId), api.imaging(patientId)])
      .then(([l, i]) => {
        setLabs(l);
        setImaging(i);
        setMetaLoaded(true);
      })
      .catch(() => setMetaLoaded(true));
  }, [open, patientId, metaLoaded]);

  useEffect(() => {
    if (!open || selectedId == null) return;
    let cancelled = false;
    setLoadingVisit(true);
    setError('');
    setPdfUrl(prev => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    api.visit(selectedId)
      .then(v => {
        if (!cancelled) setDetail(v);
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load visit');
      })
      .finally(() => {
        if (!cancelled) setLoadingVisit(false);
      });
    return () => { cancelled = true; };
  }, [open, selectedId]);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const flashCopied = (label: string) => {
    setCopied(label);
    window.setTimeout(() => setCopied(''), 1600);
  };

  const copyField = (label: string, value: string | null | undefined, key: keyof CopyTarget) => {
    if (!value?.trim() || !onCopyToForm) return;
    onCopyToForm({ [key]: value });
    flashCopied(label);
  };

  const loadPdf = async () => {
    if (!selectedId) return;
    setPdfLoading(true);
    setError('');
    try {
      const blob = await api.fetchPrescriptionPdf(selectedId);
      setPdfUrl(prev => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(blob);
      });
      setTab('rx');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load prescription PDF');
    } finally {
      setPdfLoading(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <div className="old-reports-backdrop" onClick={onClose} />
      <aside
        className="old-reports-drawer"
        role="dialog"
        aria-label="Old reports"
        style={{ width: `min(${drawerWidth}px, 100vw)` }}
      >
        <button
          type="button"
          className="old-reports-resize"
          title="Drag to resize"
          aria-label="Resize Old Reports panel"
          onMouseDown={onResizeStart}
        />
        <header>
          <div>
            <h5><i className="fas fa-folder-open me-2"></i>Old Reports</h5>
            <p>{patientName} · {priorVisits.length} prior visit{priorVisits.length === 1 ? '' : 's'}</p>
          </div>
          <div className="d-flex align-items-center gap-1">
            <div className="btn-group btn-group-sm old-reports-width-presets" role="group" aria-label="Panel width">
              <button type="button" className="btn btn-light" title="Narrow" onClick={() => setWidthPersist(420)}>S</button>
              <button type="button" className="btn btn-light" title="Wide" onClick={() => setWidthPersist(Math.round(window.innerWidth * 0.55))}>M</button>
              <button type="button" className="btn btn-light" title="Almost full width" onClick={() => setWidthPersist(Math.round(window.innerWidth * 0.9))}>L</button>
            </div>
            <button type="button" className="btn btn-sm btn-light" onClick={onClose} aria-label="Close">
              <i className="fas fa-times"></i>
            </button>
          </div>
        </header>

        <div className="old-reports-tabs">
          {([
            { id: 'visits' as const, label: 'Visits', icon: 'notes-medical' },
            { id: 'rx' as const, label: 'Rx', icon: 'prescription' },
            { id: 'labs' as const, label: 'Labs', icon: 'flask' },
            { id: 'imaging' as const, label: 'Imaging', icon: 'x-ray' },
          ]).map(t => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? 'active' : ''}
              onClick={() => setTab(t.id)}
            >
              <i className={`fas fa-${t.icon} me-1`}></i>{t.label}
            </button>
          ))}
        </div>

        <div className="old-reports-body">
          {error && <div className="alert alert-danger py-2 small">{error}</div>}
          {copied && (
            <div className="alert alert-success py-2 small">
              Copied {copied} into the current case sheet
            </div>
          )}

          {(tab === 'visits' || tab === 'rx') && priorVisits.length === 0 ? (
            <div className="text-muted text-center py-5">No prior visits for this patient.</div>
          ) : (
            <>
              {(tab === 'visits' || tab === 'rx') && priorVisits.length > 0 && (
                <div className="mb-3">
                  {priorVisits.map(v => (
                    <button
                      key={v.id}
                      type="button"
                      className={`visit-chip ${selectedId === v.id ? 'active' : ''}`}
                      onClick={() => setSelectedId(v.id)}
                    >
                      <div className="d-flex justify-content-between gap-2">
                        <strong>{formatDate(v.visit_date)}</strong>
                        <span className="badge badge-soft">{v.visit_type}</span>
                      </div>
                      <div className="small text-muted mt-1 text-truncate">
                        {v.diagnosis || v.chief_complaints || 'No diagnosis recorded'}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {tab === 'visits' && (
                loadingVisit ? (
                  <div className="text-center text-muted py-4">Loading visit…</div>
                ) : detail ? (
                  <>
                    {onCopyToForm && (
                      <div className="copy-row">
                        <button type="button" className="btn btn-sm btn-outline-primary"
                          disabled={!detail.diagnosis}
                          onClick={() => copyField('diagnosis', detail.diagnosis, 'diagnosis')}>
                          Copy diagnosis
                        </button>
                        <button type="button" className="btn btn-sm btn-outline-primary"
                          disabled={!detail.chief_complaints}
                          onClick={() => copyField('complaints', detail.chief_complaints, 'chief_complaints')}>
                          Copy complaints
                        </button>
                        <button type="button" className="btn btn-sm btn-outline-primary"
                          disabled={!detail.investigation}
                          onClick={() => copyField('investigations', detail.investigation, 'investigation')}>
                          Copy investigations
                        </button>
                        <button type="button" className="btn btn-sm btn-outline-primary"
                          disabled={!detail.history}
                          onClick={() => copyField('history', detail.history, 'history')}>
                          Copy history
                        </button>
                        <button type="button" className="btn btn-sm btn-outline-primary"
                          disabled={!detail.examination}
                          onClick={() => copyField('examination', detail.examination, 'examination')}>
                          Copy examination
                        </button>
                      </div>
                    )}

                    <div className="report-section">
                      <h6>Diagnosis</h6>
                      <p>{detail.diagnosis || '—'}</p>
                    </div>
                    <div className="report-section">
                      <h6>Chief complaints</h6>
                      <p>{detail.chief_complaints || '—'}</p>
                    </div>
                    <div className="report-section">
                      <h6>Vitals</h6>
                      <p>
                        {[
                          detail.height != null && `Ht ${detail.height} cm`,
                          detail.weight != null && `Wt ${detail.weight} kg`,
                          detail.bmi != null && `BMI ${detail.bmi}`,
                          detail.bp_systolic != null && `BP ${detail.bp_systolic}/${detail.bp_diastolic ?? '—'}`,
                          detail.pulse != null && `Pulse ${detail.pulse}`,
                        ].filter(Boolean).join(' · ') || '—'}
                      </p>
                    </div>
                    <div className="report-section">
                      <h6>History</h6>
                      <p>{detail.history || '—'}</p>
                    </div>
                    <div className="report-section">
                      <h6>Examination</h6>
                      <p>{detail.examination || '—'}</p>
                    </div>
                    <div className="report-section">
                      <h6>Investigations</h6>
                      <p>{detail.investigation || detail.investigations_text || '—'}</p>
                    </div>
                    {detail.comorbidities && (
                      <div className="report-section">
                        <h6>Comorbidities</h6>
                        <p>{detail.comorbidities}</p>
                      </div>
                    )}
                    {detail.specialty_fields && detail.specialty_fields.length > 0 && (
                      <div className="report-section">
                        <h6>Specialty findings</h6>
                        {detail.specialty_fields.map(f => (
                          <div key={f.key} className="small mb-1">
                            <strong>{f.label}:</strong> {f.value || '—'}
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="report-section">
                      <h6>Prescriptions ({detail.prescriptions.length})</h6>
                      {detail.prescriptions.length === 0 ? (
                        <p className="text-muted">No medications on this visit.</p>
                      ) : detail.prescriptions.map(rx => (
                        <div className="rx-row" key={rx.id}>
                          <div>
                            <strong>{drugLabel(rx)}</strong>
                            {rx.generic_name && <div className="text-muted small">{rx.generic_name}</div>}
                          </div>
                          <div className="text-muted">
                            {[rx.formatted_dosage || rx.dosage, rx.frequency, rx.timing, rx.duration]
                              .filter(Boolean).join(' · ') || '—'}
                          </div>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="btn btn-sm btn-primary mt-2"
                        disabled={pdfLoading || detail.prescriptions.length === 0}
                        onClick={loadPdf}
                      >
                        {pdfLoading ? 'Loading PDF…' : 'View Rx PDF'}
                      </button>
                    </div>
                  </>
                ) : null
              )}

              {tab === 'rx' && (
                <>
                  {detail && (
                    <div className="report-section mb-3">
                      <div className="d-flex justify-content-between align-items-center mb-2">
                        <h6 className="mb-0">Rx · {formatDate(detail.visit_date)}</h6>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-primary"
                          disabled={pdfLoading || detail.prescriptions.length === 0}
                          onClick={loadPdf}
                        >
                          {pdfLoading ? 'Loading…' : 'Refresh PDF'}
                        </button>
                      </div>
                      {detail.prescriptions.length === 0 ? (
                        <p className="text-muted mb-0">No prescription for this visit.</p>
                      ) : detail.prescriptions.map(rx => (
                        <div className="rx-row" key={rx.id}>
                          <div><strong>{drugLabel(rx)}</strong></div>
                          <div className="text-muted small">
                            {[rx.formatted_dosage || rx.dosage, rx.frequency, rx.duration]
                              .filter(Boolean).join(' · ')}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {pdfUrl ? (
                    <iframe title="Prescription PDF" src={pdfUrl} style={{ width: '100%', height: '55vh', border: '1px solid var(--line)', borderRadius: 12 }} />
                  ) : (
                    <div className="text-muted text-center py-4 small">
                      Select a visit and tap <strong>View Rx PDF</strong> to preview without leaving this page.
                    </div>
                  )}
                </>
              )}

              {tab === 'labs' && (
                labs.length === 0 ? (
                  <div className="text-muted text-center py-4">No lab results recorded.</div>
                ) : (
                  <div className="report-section p-0 overflow-hidden">
                    <div className="px-3 pt-2 pb-1 small text-muted d-flex flex-wrap gap-2 align-items-center">
                      <span>Rows = lab parameters · columns = dates</span>
                      <span className="ms-auto">
                        <span className="lab-flag-swatch high" /> High
                        <span className="lab-flag-swatch low ms-2" /> Low
                      </span>
                      <span className="text-muted">Drag left edge or use S/M/L to widen</span>
                    </div>
                    <div className="table-responsive old-reports-labs-scroll">
                      <table className="table table-sm old-reports-labs-table old-reports-labs-matrix mb-0">
                        <thead>
                          <tr>
                            <th className="lab-param-col sticky-col">Parameter</th>
                            <th className="lab-unit-col">Unit</th>
                            {labMatrix.dates.map(d => (
                              <th key={d} className="text-center text-nowrap">{formatDate(d)}</th>
                            ))}
                            <th className="lab-ref-col">Reference</th>
                          </tr>
                        </thead>
                        <tbody>
                          {labMatrix.rows.map(row => (
                            <tr key={row.test_name}>
                              <th scope="row" className="lab-param-col sticky-col fw-semibold">{row.test_name}</th>
                              <td className="lab-unit-col text-muted small">{row.unit || '—'}</td>
                              {labMatrix.dates.map(d => {
                                const cell = row.cells[d];
                                const flag = cell?.flag;
                                return (
                                  <td
                                    key={d}
                                    className={`text-center lab-value-cell${flag ? ` lab-${flag}` : ''}`}
                                    title={flag ? `${flag.toUpperCase()} vs ${row.reference_range}` : undefined}
                                  >
                                    {cell?.value ?? '—'}
                                  </td>
                                );
                              })}
                              <td className="lab-ref-col small text-muted">{row.reference_range || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )
              )}

              {tab === 'imaging' && (
                imaging.length === 0 ? (
                  <div className="text-muted text-center py-4">No imaging reports recorded.</div>
                ) : imaging.map(img => (
                  <div className="report-section" key={img.id}>
                    <h6>{img.study_type} · {formatDate(img.report_date)}</h6>
                    <p>{img.findings || '—'}</p>
                  </div>
                ))
              )}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
