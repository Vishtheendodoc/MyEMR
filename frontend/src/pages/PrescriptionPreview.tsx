import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, PdfLayout, VisitDetail } from '../api/client';
import { formatClinicDate } from '../utils/clinicTime';

type PreviewMode = 'pdf' | 'html';

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function LayoutSlider({
  label,
  icon,
  value,
  min,
  max,
  unit,
  onChange,
}: {
  label: string;
  icon: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="d-flex align-items-center gap-2 flex-wrap">
      <label className="form-label mb-0 text-nowrap">
        <i className={`fas ${icon} me-1`}></i>{label}:
      </label>
      <input
        type="range"
        className="form-range"
        style={{ width: 100 }}
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
      />
      <input
        type="number"
        className="form-control form-control-sm"
        style={{ width: 65 }}
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(clamp(Number(e.target.value) || min, min, max))}
      />
      <span className="text-muted small">{unit}</span>
    </div>
  );
}

export default function PrescriptionPreview() {
  const { id } = useParams<{ id: string }>();
  const visitId = Number(id);
  const [visit, setVisit] = useState<VisitDetail | null>(null);
  const [fontSize, setFontSize] = useState(12);
  const [headerSpace, setHeaderSpace] = useState(0);
  const [leftMargin, setLeftMargin] = useState(12);
  const [hidePatientInfo, setHidePatientInfo] = useState(false);
  const [hideHeader, setHideHeader] = useState(false);
  const [mode, setMode] = useState<PreviewMode>('pdf');
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [htmlContent, setHtmlContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const pdfUrlRef = useRef<string | null>(null);

  const layout = useCallback((): PdfLayout => ({
    font_size: fontSize,
    header_space: headerSpace,
    left_margin: leftMargin,
    hide_patient_info: hidePatientInfo,
    hide_header: hideHeader,
  }), [fontSize, headerSpace, leftMargin, hidePatientInfo, hideHeader]);

  const refreshPreview = useCallback(async (layoutOverride?: PdfLayout) => {
    if (!id) return;
    const activeLayout = layoutOverride ?? layout();
    setLoading(true);
    setError('');
    try {
      const blob = await api.fetchPrescriptionPdf(visitId, activeLayout);
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
      const url = URL.createObjectURL(blob);
      pdfUrlRef.current = url;
      setPdfUrl(url);

      const html = await api.fetchPrescriptionHtml(visitId, activeLayout);
      setHtmlContent(html);

      const updated = await api.visit(visitId);
      setVisit(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Preview failed');
    } finally {
      setLoading(false);
    }
  }, [id, visitId, layout]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    (async () => {
      try {
        const v = await api.visit(visitId);
        if (cancelled) return;

        const hidePt = v.pdf_hide_patient_info === true;
        const hideHd = v.pdf_hide_header === true;
        const fs = v.pdf_font_size ?? 12;
        const hs = v.pdf_header_space ?? 0;
        const lm = v.pdf_left_margin ?? 12;
        const initialLayout: PdfLayout = {
          font_size: fs,
          header_space: hs,
          left_margin: lm,
          hide_patient_info: hidePt,
          hide_header: hideHd,
        };

        setVisit(v);
        setFontSize(fs);
        setHeaderSpace(hs);
        setLeftMargin(lm);
        setHidePatientInfo(hidePt);
        setHideHeader(hideHd);

        setLoading(true);
        setError('');
        const blob = await api.fetchPrescriptionPdf(visitId, initialLayout);
        if (cancelled) return;
        if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
        const url = URL.createObjectURL(blob);
        pdfUrlRef.current = url;
        setPdfUrl(url);
        const html = await api.fetchPrescriptionHtml(visitId, initialLayout);
        if (cancelled) return;
        setHtmlContent(html);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Preview failed');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
    };
  }, [id, visitId]);

  const handleApply = () => refreshPreview();

  const handleDownload = async () => {
    const blob = await api.fetchPrescriptionPdf(visitId, layout(), true);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `prescription_${visit?.patient_name}_${id}${visit?.status !== 'locked' ? '_DRAFT' : ''}.pdf`.replace(/\s/g, '_');
    a.click();
  };

  const sendWhatsApp = async () => {
    setError('');
    try {
      const result = await api.whatsappPrescription(visitId);
      if (result.whatsapp_url) window.open(result.whatsapp_url, '_blank');
      else setError('WhatsApp link not available for this patient.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'WhatsApp failed');
    }
  };

  const handlePrint = () => {
    if (mode === 'pdf' && iframeRef.current?.contentWindow) {
      try {
        iframeRef.current.contentWindow.focus();
        iframeRef.current.contentWindow.print();
        return;
      } catch {
        /* fall through */
      }
    }
    const w = window.open('', '_blank');
    if (!w) {
      alert('Please allow pop-ups to print the prescription.');
      return;
    }
    w.document.write(htmlContent);
    w.document.close();
    w.focus();
    w.print();
  };

  if (!visit) return <div className="py-5 text-center">Loading...</div>;

  return (
    <div>
      <div className="mb-3">
        <h2><i className="fas fa-file-medical me-2"></i>Prescription Preview</h2>
        <p className="text-muted mb-0">
          <strong>Patient:</strong> {visit.patient_name}
          {' | '}
          <strong>Visit:</strong> {formatClinicDate(visit.visit_date)}
          {visit.pdf_page_count != null && (
            <span className="badge bg-info ms-2">
              {visit.pdf_page_count} page{visit.pdf_page_count !== 1 ? 's' : ''}
            </span>
          )}
          {visit.status !== 'locked' && (
            <span className="badge bg-warning text-dark ms-2">Draft on print/PDF</span>
          )}
        </p>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card mb-3 p-3 bg-light border">
        <div className="d-flex flex-wrap gap-3 align-items-center justify-content-between">
          <div className="d-flex flex-wrap gap-3 align-items-center">
            <div className="btn-group">
              <button
                type="button"
                className={`btn btn-sm ${mode === 'pdf' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setMode('pdf')}
              >
                <i className="fas fa-file-pdf me-1"></i>PDF Preview
              </button>
              <button
                type="button"
                className={`btn btn-sm ${mode === 'html' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setMode('html')}
              >
                <i className="fas fa-eye me-1"></i>HTML Preview
              </button>
            </div>

            <LayoutSlider
              label="Font"
              icon="fa-text-height"
              value={fontSize}
              min={9}
              max={16}
              unit="pt"
              onChange={setFontSize}
            />
            <LayoutSlider
              label="Top space"
              icon="fa-arrows-alt-v"
              value={headerSpace}
              min={0}
              max={100}
              unit="mm"
              onChange={setHeaderSpace}
            />
            <LayoutSlider
              label="Left margin"
              icon="fa-arrows-alt-h"
              value={leftMargin}
              min={0}
              max={40}
              unit="mm"
              onChange={setLeftMargin}
            />

            <div className="form-check ms-2">
              <input className="form-check-input" type="checkbox" id="hidePatient"
                checked={hidePatientInfo} onChange={e => setHidePatientInfo(e.target.checked)} />
              <label className="form-check-label small" htmlFor="hidePatient">
                Hide patient info
              </label>
            </div>
            <div className="form-check ms-2">
              <input className="form-check-input" type="checkbox" id="hideHeader"
                checked={hideHeader} onChange={e => setHideHeader(e.target.checked)} />
              <label className="form-check-label small" htmlFor="hideHeader">
                Hide prescription header
              </label>
            </div>

            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={handleApply} disabled={loading}>
              {loading ? 'Applying...' : 'Apply'}
            </button>
          </div>

          <div className="d-flex flex-wrap gap-2">
            <Link to={`/visits/${visit.id}`} className="btn btn-sm btn-secondary">
              <i className="fas fa-arrow-left me-1"></i>Back to Visit
            </Link>
            <button type="button" className="btn btn-sm btn-success" onClick={handleDownload}>
              <i className="fas fa-download me-1"></i>Download PDF
            </button>
            <button type="button" className="btn btn-sm btn-warning" onClick={handlePrint}>
              <i className="fas fa-print me-1"></i>Print
            </button>
            <button type="button" className="btn btn-sm btn-success" onClick={sendWhatsApp}>
              <i className="fab fa-whatsapp me-1"></i>WhatsApp Rx
            </button>
          </div>
        </div>
        <p className="small text-muted mb-0 mt-2">
          Adjust <strong>font</strong>, <strong>top space</strong> (0–100 mm for letterhead), <strong>left margin</strong>, and patient info visibility, then click <strong>Apply</strong>.
        </p>
      </div>

      {mode === 'pdf' ? (
        <div className="rounded p-2" style={{ background: '#e9ecef', minHeight: '75vh' }}>
          {pdfUrl ? (
            <iframe
              ref={iframeRef}
              title="Prescription PDF"
              src={pdfUrl}
              className="w-100 border-0 rounded bg-white shadow-sm"
              style={{ minHeight: '72vh' }}
            />
          ) : (
            <div className="text-center py-5 text-muted">Generating preview...</div>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="card-header bg-light small text-muted">
            HTML layout at {fontSize} pt, top space {headerSpace} mm, left margin {leftMargin} mm
          </div>
          <div className="card-body p-3" dangerouslySetInnerHTML={{ __html: htmlContent }} />
        </div>
      )}
    </div>
  );
}
