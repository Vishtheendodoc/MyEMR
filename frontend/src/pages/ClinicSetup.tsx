import { useEffect, useState } from 'react';
import { api, ClinicProfile, PriceItem } from '../api/client';

const EMPTY_PRICE = { kind: 'service', name: '', code: '', rate: '', gst_percent: '0', detail: '' };

export default function ClinicSetup() {
  const [profile, setProfile] = useState<ClinicProfile | null>(null);
  const [prices, setPrices] = useState<PriceItem[]>([]);
  const [form, setForm] = useState(EMPTY_PRICE);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = async () => {
    const [clinic, list] = await Promise.all([api.clinicProfile(), api.prices()]);
    setProfile(clinic);
    setPrices(list);
  };

  useEffect(() => {
    load().catch(err => setError(err instanceof Error ? err.message : 'Failed to load clinic setup'));
  }, []);

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setError('');
    try {
      const saved = await api.saveClinicProfile(profile);
      setProfile(saved);
      setSuccess('Letterhead saved. Prescriptions and invoices use it.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save letterhead');
    }
  };

  const addPrice = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await api.savePrice({
        kind: form.kind,
        name: form.name,
        code: form.code || null,
        rate: Number(form.rate) || 0,
        gst_percent: Number(form.gst_percent) || 0,
        detail: form.detail || null,
        active: true,
      });
      setForm(EMPTY_PRICE);
      setSuccess('Price saved.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save price');
    }
  };

  const onSignature = (file?: File) => {
    if (!file || !profile) return;
    if (file.size > 200_000) {
      setError('Use a signature image under 200 KB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setProfile({ ...profile, signature_data: String(reader.result || '') });
    reader.readAsDataURL(file);
  };

  if (!profile) return <div className="text-muted py-4">Loading clinic setup…</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Clinic setup</h2>
          <p className="page-subtitle">Your letterhead, prices, and favorites. Another doctor’s setup stays separate. ABDM and ABHA are not connected.</p>
        </div>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="card p-3 mb-4" style={{ maxWidth: 720 }}>
        <h5>Letterhead</h5>
        <form onSubmit={saveProfile}>
          <input className="form-control mb-2" placeholder="Clinic name" required value={profile.name} onChange={e => setProfile({ ...profile, name: e.target.value })} />
          <textarea className="form-control mb-2" rows={2} placeholder="Address" value={profile.address || ''} onChange={e => setProfile({ ...profile, address: e.target.value })} />
          <div className="row g-2 mb-2">
            <div className="col-md-6"><input className="form-control" placeholder="Phone" value={profile.phone || ''} onChange={e => setProfile({ ...profile, phone: e.target.value })} /></div>
            <div className="col-md-6"><input className="form-control" placeholder="GSTIN" value={profile.gstin || ''} onChange={e => setProfile({ ...profile, gstin: e.target.value })} /></div>
          </div>
          <input className="form-control mb-2" placeholder="Name under the signature" value={profile.signatory || ''} onChange={e => setProfile({ ...profile, signatory: e.target.value })} />
          <label className="form-label small">Signature image</label>
          <input className="form-control mb-2" type="file" accept="image/*" onChange={e => onSignature(e.target.files?.[0])} />
          {profile.signature_data && <img src={profile.signature_data} alt="Signature" style={{ maxHeight: 70 }} className="mb-2 d-block" />}
          <button className="btn btn-primary">Save letterhead</button>
        </form>
      </div>

      <div className="row">
        <div className="col-lg-7 mb-4">
          <div className="card">
            <div className="card-header"><h5 className="mb-0">Price list</h5></div>
            <div className="table-responsive">
              <table className="table mb-0">
                <thead><tr><th>Type</th><th>Name</th><th>Code</th><th>Rate</th><th></th></tr></thead>
                <tbody>
                  {prices.map(item => (
                    <tr key={item.id}>
                      <td className="small">{item.kind}</td>
                      <td>
                        <div>{item.name}</div>
                        {item.detail && <div className="small text-muted">{item.detail}</div>}
                      </td>
                      <td className="small">{item.code || '—'}</td>
                      <td>{item.kind === 'favorite' ? '—' : `₹${item.rate}`}</td>
                      <td><button type="button" className="btn btn-sm btn-outline-danger" onClick={() => api.deletePrice(item.id).then(load)}>Remove</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="col-lg-5">
          <div className="card p-3">
            <h5>Add</h5>
            <form onSubmit={addPrice}>
              <select className="form-select mb-2" value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}>
                <option value="service">Service or test</option>
                <option value="panel">Test panel</option>
                <option value="medicine">Medicine rate</option>
                <option value="favorite">Favorite prescription</option>
              </select>
              <input className="form-control mb-2" placeholder="Name" required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              {form.kind !== 'favorite' && (
                <div className="row g-2 mb-2">
                  <div className="col-4"><input className="form-control" placeholder="SAC/HSN" value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} /></div>
                  <div className="col-4"><input className="form-control" type="number" min="0" placeholder="Rate" value={form.rate} onChange={e => setForm({ ...form, rate: e.target.value })} /></div>
                  <div className="col-4"><input className="form-control" type="number" min="0" placeholder="GST %" value={form.gst_percent} onChange={e => setForm({ ...form, gst_percent: e.target.value })} /></div>
                </div>
              )}
              <textarea className="form-control mb-2" rows={3} placeholder={form.kind === 'favorite' ? 'One medicine name per line' : form.kind === 'panel' ? 'Tests in this panel, one per line' : 'Optional note'} value={form.detail} onChange={e => setForm({ ...form, detail: e.target.value })} />
              <button className="btn btn-primary w-100">Add to price list</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
