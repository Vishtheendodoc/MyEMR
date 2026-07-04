import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ImagingResult, LabResult, PatientDetail } from '../api/client';

export default function PatientLabs() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [imaging, setImaging] = useState<ImagingResult[]>([]);
  const [labForm, setLabForm] = useState({ test_name: '', value: '', unit: '', reference_range: '' });
  const [imgForm, setImgForm] = useState({ study_type: '', findings: '' });

  const load = () => {
    if (!id) return;
    const pid = Number(id);
    api.patient(pid).then(setPatient);
    api.labs(pid).then(setLabs);
    api.imaging(pid).then(setImaging);
  };

  useEffect(() => { load(); }, [id]);

  const addLab = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.addLab(Number(id), labForm);
    setLabForm({ test_name: '', value: '', unit: '', reference_range: '' });
    load();
  };

  const addImaging = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.addImaging(Number(id), imgForm);
    setImgForm({ study_type: '', findings: '' });
    load();
  };

  if (!patient) return <div>Loading...</div>;

  return (
    <div>
      <div className="d-flex justify-content-between mb-4">
        <h2>Labs & Imaging — {patient.name}</h2>
        <Link to={`/patients/${patient.id}`} className="btn btn-outline-secondary">Back</Link>
      </div>

      <div className="row">
        <div className="col-md-6 mb-4">
          <div className="card">
            <div className="card-header"><h5 className="mb-0">Lab Results</h5></div>
            <div className="table-responsive">
              <table className="table mb-0">
                <thead><tr><th>Test</th><th>Value</th><th>Date</th><th></th></tr></thead>
                <tbody>
                  {labs.map(l => (
                    <tr key={l.id}>
                      <td>{l.test_name}</td>
                      <td>{l.value} {l.unit}</td>
                      <td>{new Date(l.result_date).toLocaleDateString()}</td>
                      <td><button className="btn btn-sm btn-outline-danger" onClick={() => api.deleteLab(l.id).then(load)}>×</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card-body border-top">
              <form onSubmit={addLab} className="row g-2">
                <div className="col-6"><input className="form-control" placeholder="Test name" required value={labForm.test_name} onChange={e => setLabForm({ ...labForm, test_name: e.target.value })} /></div>
                <div className="col-3"><input className="form-control" placeholder="Value" required value={labForm.value} onChange={e => setLabForm({ ...labForm, value: e.target.value })} /></div>
                <div className="col-3"><input className="form-control" placeholder="Unit" value={labForm.unit} onChange={e => setLabForm({ ...labForm, unit: e.target.value })} /></div>
                <div className="col-12"><button className="btn btn-primary btn-sm">Add Lab</button></div>
              </form>
            </div>
          </div>
        </div>

        <div className="col-md-6 mb-4">
          <div className="card">
            <div className="card-header"><h5 className="mb-0">Imaging</h5></div>
            <div className="list-group list-group-flush">
              {imaging.length === 0 ? (
                <div className="list-group-item text-muted">No imaging records</div>
              ) : imaging.map(img => (
                <div className="list-group-item" key={img.id}>
                  <strong>{img.study_type}</strong>
                  <div className="small text-muted">{new Date(img.report_date).toLocaleDateString()}</div>
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
      </div>
    </div>
  );
}
