import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, CdsRecommendation, VisitDetail } from '../api/client';
import { formatClinicDate, formatClinicDateTime } from '../utils/clinicTime';
import { followUpNotesForDisplay } from '../utils/followUpNotes';

export default function VisitDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [visit, setVisit] = useState<VisitDetail | null>(null);
  const [cds, setCds] = useState<CdsRecommendation[]>([]);

  const load = () => {
    if (id) {
      api.visit(Number(id)).then(setVisit);
      api.visitCds(Number(id)).then(setCds).catch(() => setCds([]));
    }
  };

  useEffect(() => { load(); }, [id]);

  if (!visit) return <div>Loading...</div>;

  const followUpNotes = followUpNotesForDisplay(visit.follow_up_notes, visit.follow_up_date);

  const hasInvestigations = Boolean(visit.investigations_text?.trim());
  const hasMedications = visit.prescriptions.length > 0;
  const canFinalize = visit.can_finalize ?? (hasMedications || hasInvestigations
    || Boolean(visit.follow_up_date || visit.follow_up_notes?.trim()));

  const finalizeMessage = hasMedications
    ? 'Finalize and lock this visit? No further edits will be allowed.'
    : 'Finalize this investigations-only visit? No medications are added yet — you will not be able to add them after locking.';

  const severityClass = (s: string) => s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'info';

  return (
    <div>
      <div className="d-flex justify-content-between mb-4">
        <h2>Visit — {visit.patient_name}</h2>
        <div>
          {visit.status === 'locked' ? (
            <span className="badge bg-secondary me-2"><i className="fas fa-lock me-1"></i>Finalized & Locked</span>
          ) : (
            <>
              <span className="badge bg-warning text-dark me-2">Draft</span>
              <Link to={`/visits/${visit.id}/edit`} className="btn btn-outline-secondary me-2">
                <i className="fas fa-edit me-1"></i>Edit Case Sheet
              </Link>
              {canFinalize && (
                <button className="btn btn-success me-2" onClick={async () => {
                  if (!confirm(finalizeMessage)) return;
                  await api.finalizeVisit(visit.id);
                  load();
                }}>
                  <i className="fas fa-lock me-1"></i>Finalize Visit
                </button>
              )}
              <Link to={`/visits/${visit.id}/prescribe`} className="btn btn-primary me-2">
                <i className="fas fa-prescription me-1"></i>Prescribe
              </Link>
            </>
          )}
          <Link to={`/visits/${visit.id}/prescription-preview`} className="btn btn-outline-primary me-2">
            <i className="fas fa-file-medical me-1"></i>Prescription Preview
          </Link>
          {visit.pdf_page_count != null && (
            <span className="badge bg-secondary align-middle">{visit.pdf_page_count} page PDF</span>
          )}
        </div>
      </div>

      {visit.status !== 'locked' && hasInvestigations && !hasMedications && (
        <div className="alert alert-info">
          <i className="fas fa-flask me-1"></i>
          Investigations recorded — medications are optional for now. Use <strong>Prescription Preview</strong> to print
          investigation orders, add medications later via <strong>Prescribe</strong>, then finalize when ready.
        </div>
      )}

      {cds.length > 0 && (
        <div className="card mb-4">
          <div className="card-header bg-light"><h5 className="mb-0"><i className="fas fa-brain me-2"></i>Clinical Decision Support</h5></div>
          <div className="list-group list-group-flush">
            {cds.map((c, i) => (
              <div className={`list-group-item border-start border-4 border-${severityClass(c.severity)}`} key={i}>
                <div className="d-flex justify-content-between">
                  <strong>{c.category}</strong>
                  <span className={`badge bg-${severityClass(c.severity)}`}>{c.severity}</span>
                </div>
                <small className="text-muted">{c.source}</small>
                <p className="mb-0 mt-1">{c.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {visit.warnings.length > 0 && (
        <div className="alert alert-warning">
          <strong><i className="fas fa-exclamation-triangle me-1"></i>Drug Warnings:</strong>
          <ul className="mb-0 mt-2">
            {visit.warnings.map((w, i) => (
              <li key={i}>{w.drug} + {w.comorbidity}: {w.recommendation}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card mb-4 p-3">
        <div className="row">
          <div className="col-md-3"><strong>Date:</strong> {formatClinicDateTime(visit.visit_date)}</div>
          <div className="col-md-3"><strong>Type:</strong> {visit.visit_type}</div>
          <div className="col-md-3"><strong>MRD:</strong> {visit.patient_mrd || '-'}</div>
          {visit.bmi && <div className="col-md-3"><strong>BMI:</strong> {visit.bmi}</div>}
        </div>
        {visit.specialty_template && (
          <div className="mt-2">
            <span className="badge bg-info text-capitalize">{visit.specialty_template} template</span>
          </div>
        )}
        <hr />
        <p><strong>Chief Complaints:</strong> {visit.chief_complaints}</p>
        {visit.diagnosis && <p><strong>Diagnosis:</strong> {visit.diagnosis}</p>}

        {visit.specialty_fields && visit.specialty_fields.length > 0 && (
          <div className="card bg-light mb-3">
            <div className="card-body py-2">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h6 className="mb-0 text-capitalize">{visit.specialty_template} Visit Data</h6>
                <Link to={`/patients/${visit.patient_id}/labs`} className="btn btn-sm btn-outline-primary">View in Labs</Link>
              </div>
              <table className="table table-sm mb-0">
                <tbody>
                  {visit.specialty_fields.map(f => (
                    <tr key={f.key}>
                      <td className="text-muted" style={{ width: '40%' }}>{f.label}</td>
                      <td><strong>{f.value}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {visit.comorbidities && <p><strong>Comorbidities:</strong> {visit.comorbidities}</p>}
        {visit.history && <p><strong>History:</strong> {visit.history}</p>}
        {visit.examination && <p><strong>Examination:</strong> {visit.examination}</p>}
      </div>

      {visit.investigations_text && (
        <div className="card mb-4 p-3">
          <h6 className="mb-2">Current Investigations</h6>
          <div className="border rounded p-3 bg-light" style={{ whiteSpace: 'pre-line' }}>
            {visit.investigations_text}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Prescriptions{visit.status !== 'locked' && !hasMedications && <span className="text-muted small ms-2">(optional — add after investigations)</span>}</h5>
        </div>
        <div className="table-responsive">
          <table className="table mb-0">
            <thead>
              <tr><th>Drug</th><th>Generic</th><th>Dosage</th><th>Frequency</th><th>Timing</th><th>Duration</th><th></th></tr>
            </thead>
            <tbody>
              {visit.prescriptions.length === 0 ? (
                <tr><td colSpan={7} className="text-center text-muted">No medications yet — use Prescribe when ready</td></tr>
              ) : visit.prescriptions.map(rx => (
                <tr key={rx.id}>
                  <td>{rx.drug_name}</td>
                  <td>{rx.generic_name}</td>
                  <td>{rx.formatted_dosage}</td>
                  <td>{rx.frequency}</td>
                  <td>{rx.timing || '-'}</td>
                  <td>{rx.duration}</td>
                  <td>
                    {visit.status !== 'locked' && (
                      <button className="btn btn-sm btn-outline-danger"
                        onClick={async () => { await api.deletePrescription(rx.id); load(); }}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {(visit.follow_up_date || followUpNotes) && (
        <div className="card mt-4 p-3">
          <h6 className="mb-2">Follow-up</h6>
          {visit.follow_up_date && (
            <p className="mb-1">
              <strong>Next Visit:</strong>{' '}
              {formatClinicDate(visit.follow_up_date)}
            </p>
          )}
          {followUpNotes && <p className="mb-0"><strong>Notes:</strong> {followUpNotes}</p>}
        </div>
      )}

      <div className="mt-3">
        <Link to={`/patients/${visit.patient_id}`} className="btn btn-outline-secondary">Back to Patient</Link>
      </div>
    </div>
  );
}
