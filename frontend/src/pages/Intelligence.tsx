import { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ClinicalAlert } from '../api/client';

export default function Intelligence() {
  const { id } = useParams<{ id: string }>();
  const [alerts, setAlerts] = useState<ClinicalAlert[]>([]);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    if (!id) return;
    api.intelligence(Number(id)).then(data => setAlerts(data.alerts)).catch(err => setError(err.message));
  };

  useEffect(load, [id]);

  const dismiss = (event: FormEvent, alertId: number) => {
    event.preventDefault();
    api.dismissAlert(alertId, reason).then(load).catch(err => setError(err.message));
  };

  return (
    <div>
      <div className="d-flex justify-content-between mb-3">
        <div>
          <h2>Clinical review</h2>
          <p className="text-muted mb-0">These prompts compare stored results with versioned rules. They do not diagnose or change a prescription.</p>
        </div>
        <Link to={`/patients/${id}`} className="btn btn-outline-secondary">Back</Link>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      {alerts.length === 0 && <div className="alert alert-light">No open review prompts.</div>}
      {alerts.map(alert => (
        <article className="card mb-3" key={alert.id}>
          <div className="card-body">
            <div className="d-flex justify-content-between">
              <h5>{alert.title}</h5>
              <span className={`badge ${alert.severity === 'high' ? 'bg-danger' : 'bg-warning text-dark'}`}>{alert.severity}</span>
            </div>
            <p>{alert.explanation}</p>
            <p className="mb-1"><strong>Review:</strong> {alert.recommended_review}</p>
            <p className="mb-1"><strong>Reference:</strong> {alert.guideline_reference}</p>
            <p className="small text-muted mb-2">Rule {alert.rule_code} version {alert.rule_version}</p>
            <pre className="small bg-light p-2">{alert.triggering_parameters}</pre>
            <div className="d-flex gap-2 flex-wrap">
              <button type="button" className="btn btn-outline-primary btn-sm" onClick={() => api.acknowledgeAlert(alert.id).then(load)}>Acknowledge</button>
              <form className="d-flex gap-2" onSubmit={event => dismiss(event, alert.id)}>
                <input className="form-control form-control-sm" value={reason} onChange={event => setReason(event.target.value)} placeholder="Reason to dismiss" aria-label="Dismiss reason" />
                <button className="btn btn-outline-secondary btn-sm" type="submit">Dismiss</button>
              </form>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
