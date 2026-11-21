import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ImagingResult, LabResult, PatientDetail } from '../api/client';

function formatDate(iso: string) {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: '2-digit',
  });
}

export default function PatientLabs() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [imaging, setImaging] = useState<ImagingResult[]>([]);
  const [labForm, setLabForm] = useState({ test_name: '', value: '', unit: '', reference_range: '', result_date: '' });
  const [imgForm, setImgForm] = useState({ study_type: '', findings: '' });
  const [view, setView] = useState<'matrix' | 'list'>('matrix');

  const load = () => {
    if (!id) return;
    const pid = Number(id);
    api.patient(pid).then(setPatient);
    api.labs(pid).then(setLabs);
    api.imaging(pid).then(setImaging);
  };

  useEffect(() => { load(); }, [id]);

  const matrix = useMemo(() => {
    const dates = [...new Set(labs.map(l => l.result_date.slice(0, 10)))].sort();
    const tests = [...new Set(labs.map(l => l.test_name))].sort((a, b) => a.localeCompare(b));
    const cell = new Map<string, LabResult>();
    const units = new Map<string, string>();
    for (const lab of labs) {
      const key = `${lab.test_name}||${lab.result_date.slice(0, 10)}`;
      // Prefer latest id if duplicate same day
      const prev = cell.get(key);
      if (!prev || lab.id > prev.id) cell.set(key, lab);
      if (lab.unit) units.set(lab.test_name, lab.unit);
    }
    return { dates, tests, cell, units };
  }, [labs]);

  const addLab = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.addLab(Number(id), {
      ...labForm,
      result_date: labForm.result_date || undefined,
    });
    setLabForm({ test_name: '', value: '', unit: '', reference_range: '', result_date: '' });
    load();
  };

  const addImaging = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.addImaging(Number(id), imgForm);
    setImgForm({ study_type: '', findings: '' });
    load();
  };

  if (!patient) return <div className="text-center py-5 text-muted">Loading…</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Labs & Imaging</h2>
          <p className="page-subtitle">{patient.name} · parameters vs visit dates</p>
        </div>
        <div className="d-flex gap-2">
          <div className="btn-group">
            <button type="button" className={`btn btn-sm ${view === 'matrix' ? 'btn-primary' : 'btn-outline-primary'}`} onClick={() => setView('matrix')}>Table</button>
            <button type="button" className={`btn btn-sm ${view === 'list' ? 'btn-primary' : 'btn-outline-primary'}`} onClick={() => setView('list')}>List</button>
          </div>
          <Link to={`/patients/${patient.id}/observations`} className="btn btn-outline-primary">Observations</Link>
          <Link to={`/patients/${patient.id}`} className="btn btn-outline-secondary">Back</Link>
        </div>
      </div>

      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Lab trends (parameter × date)</h5>
          <span className="badge badge-soft">{matrix.tests.length} tests · {matrix.dates.length} dates</span>
        </div>
        {labs.length === 0 ? (
          <div className="p-4 text-muted text-center">No lab results yet. Add results below.</div>
        ) : view === 'matrix' ? (
          <div className="table-responsive lab-matrix-wrap">
            <table className="table table-bordered lab-matrix mb-0">
              <thead>
                <tr>
                  <th className="lab-matrix-sticky">Parameter</th>
                  {matrix.dates.map(d => (
                    <th key={d} className="text-center text-nowrap">{formatDate(d)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.tests.map(test => (
                  <tr key={test}>
                    <th className="lab-matrix-sticky text-start">
                      {test}
                      {matrix.units.get(test) && (
                        <div className="small text-muted fw-normal">{matrix.units.get(test)}</div>
                      )}
                    </th>
                    {matrix.dates.map(d => {
                      const lab = matrix.cell.get(`${test}||${d}`);
                      return (
                        <td key={d} className="text-center">
                          {lab ? (
                            <span title={lab.reference_range ? `Ref ${lab.reference_range}` : undefined}>
                              {lab.value}
                            </span>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="table mb-0">
              <thead><tr><th>Test</th><th>Value</th><th>Ref</th><th>Date</th><th></th></tr></thead>
              <tbody>
                {labs.map(l => (
                  <tr key={l.id}>
                    <td>{l.test_name}</td>
                    <td>{l.value} {l.unit}</td>
                    <td className="small text-muted">{l.reference_range || '—'}</td>
                    <td>{formatDate(l.result_date)}</td>
                    <td><button className="btn btn-sm btn-outline-danger" onClick={() => api.deleteLab(l.id).then(load)}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="card-body border-top">
          <form onSubmit={addLab} className="row g-2 align-items-end">
            <div className="col-md-3">
              <label className="form-label small">Test</label>
              <input className="form-control" placeholder="e.g. HbA1c" required list="lab-test-names"
                value={labForm.test_name} onChange={e => setLabForm({ ...labForm, test_name: e.target.value })} />
              <datalist id="lab-test-names">
                {matrix.tests.map(t => <option key={t} value={t} />)}
              </datalist>
            </div>
            <div className="col-md-2">
              <label className="form-label small">Value</label>
              <input className="form-control" required value={labForm.value} onChange={e => setLabForm({ ...labForm, value: e.target.value })} />
            </div>
            <div className="col-md-2">
              <label className="form-label small">Unit</label>
              <input className="form-control" value={labForm.unit} onChange={e => setLabForm({ ...labForm, unit: e.target.value })} />
            </div>
            <div className="col-md-2">
              <label className="form-label small">Date</label>
              <input type="date" className="form-control" value={labForm.result_date}
                onChange={e => setLabForm({ ...labForm, result_date: e.target.value })} />
            </div>
            <div className="col-md-3">
              <button className="btn btn-primary w-100">Add lab result</button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h5 className="mb-0">Imaging</h5></div>
        <div className="list-group list-group-flush">
          {imaging.length === 0 ? (
            <div className="list-group-item text-muted">No imaging records</div>
          ) : imaging.map(img => (
            <div className="list-group-item" key={img.id}>
              <strong>{img.study_type}</strong>
              <div className="small text-muted">{formatDate(img.report_date)}</div>
              <p className="mb-0 mt-1">{img.findings}</p>
            </div>
          ))}
        </div>
        <div className="card-body border-top">
          <form onSubmit={addImaging}>
            <input className="form-control mb-2" placeholder="Study type" required value={imgForm.study_type} onChange={e => setImgForm({ ...imgForm, study_type: e.target.value })} />
            <textarea className="form-control mb-2" placeholder="Findings" rows={2} value={imgForm.findings} onChange={e => setImgForm({ ...imgForm, findings: e.target.value })} />
            <button className="btn btn-primary btn-sm">Add Imaging</button>
          </form>
        </div>
      </div>
    </div>
  );
}
