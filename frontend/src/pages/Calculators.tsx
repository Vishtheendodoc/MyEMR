import { useState } from 'react';
import { api } from '../api/client';

export default function Calculators() {
  const [egfr, setEgfr] = useState({ creatinine_mg_dl: '', age: '', sex: 'Male', is_african_american: false });
  const [homa, setHoma] = useState({ fasting_glucose_mg_dl: '', fasting_insulin_uIU_ml: '' });
  const [calcium, setCalcium] = useState({ calcium_mg_dl: '', albumin_g_dl: '' });
  const [steroid, setSteroid] = useState({ dose_mg: '', from_steroid: 'prednisolone', to_steroid: 'hydrocortisone' });
  const [results, setResults] = useState<Record<string, Record<string, unknown>>>({});

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-calculator me-2"></i>Clinical Calculators</h2>
      <div className="row">
        <div className="col-md-6 mb-4">
          <div className="card p-3">
            <h5>eGFR (CKD-EPI)</h5>
            <div className="row g-2 mb-2">
              <div className="col-6"><input type="number" className="form-control" placeholder="Creatinine (mg/dL)" value={egfr.creatinine_mg_dl} onChange={e => setEgfr({ ...egfr, creatinine_mg_dl: e.target.value })} /></div>
              <div className="col-6"><input type="number" className="form-control" placeholder="Age" value={egfr.age} onChange={e => setEgfr({ ...egfr, age: e.target.value })} /></div>
              <div className="col-6">
                <select className="form-select" value={egfr.sex} onChange={e => setEgfr({ ...egfr, sex: e.target.value })}>
                  <option>Male</option><option>Female</option>
                </select>
              </div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={async () => {
              const r = await api.calcEgfr({ ...egfr, creatinine_mg_dl: Number(egfr.creatinine_mg_dl), age: Number(egfr.age) });
              setResults({ ...results, egfr: r });
            }}>Calculate</button>
            {results.egfr && <div className="alert alert-success mt-2 mb-0">eGFR: {String(results.egfr.egfr)} — Stage {String(results.egfr.ckd_stage)}</div>}
          </div>
        </div>

        <div className="col-md-6 mb-4">
          <div className="card p-3">
            <h5>HOMA-IR</h5>
            <div className="row g-2 mb-2">
              <div className="col-6"><input type="number" className="form-control" placeholder="Fasting glucose" value={homa.fasting_glucose_mg_dl} onChange={e => setHoma({ ...homa, fasting_glucose_mg_dl: e.target.value })} /></div>
              <div className="col-6"><input type="number" className="form-control" placeholder="Fasting insulin" value={homa.fasting_insulin_uIU_ml} onChange={e => setHoma({ ...homa, fasting_insulin_uIU_ml: e.target.value })} /></div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={async () => {
              const r = await api.calcHomaIr({ fasting_glucose_mg_dl: Number(homa.fasting_glucose_mg_dl), fasting_insulin_uIU_ml: Number(homa.fasting_insulin_uIU_ml) });
              setResults({ ...results, homa: r });
            }}>Calculate</button>
            {results.homa && <div className="alert alert-success mt-2 mb-0">HOMA-IR: {String(results.homa.homa_ir)} — {String(results.homa.interpretation)}</div>}
          </div>
        </div>

        <div className="col-md-6 mb-4">
          <div className="card p-3">
            <h5>Corrected Calcium</h5>
            <div className="row g-2 mb-2">
              <div className="col-6"><input type="number" className="form-control" placeholder="Calcium" value={calcium.calcium_mg_dl} onChange={e => setCalcium({ ...calcium, calcium_mg_dl: e.target.value })} /></div>
              <div className="col-6"><input type="number" className="form-control" placeholder="Albumin" value={calcium.albumin_g_dl} onChange={e => setCalcium({ ...calcium, albumin_g_dl: e.target.value })} /></div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={async () => {
              const r = await api.calcCorrectedCalcium({ calcium_mg_dl: Number(calcium.calcium_mg_dl), albumin_g_dl: Number(calcium.albumin_g_dl) });
              setResults({ ...results, calcium: r });
            }}>Calculate</button>
            {results.calcium && <div className="alert alert-success mt-2 mb-0">Corrected Ca: {String(results.calcium.corrected_calcium_mg_dl)} mg/dL</div>}
          </div>
        </div>

        <div className="col-md-6 mb-4">
          <div className="card p-3">
            <h5>Steroid Conversion</h5>
            <div className="row g-2 mb-2">
              <div className="col-4"><input type="number" className="form-control" placeholder="Dose mg" value={steroid.dose_mg} onChange={e => setSteroid({ ...steroid, dose_mg: e.target.value })} /></div>
              <div className="col-4"><input className="form-control" value={steroid.from_steroid} onChange={e => setSteroid({ ...steroid, from_steroid: e.target.value })} /></div>
              <div className="col-4"><input className="form-control" value={steroid.to_steroid} onChange={e => setSteroid({ ...steroid, to_steroid: e.target.value })} /></div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={async () => {
              const r = await api.calcSteroid({ ...steroid, dose_mg: Number(steroid.dose_mg) });
              setResults({ ...results, steroid: r });
            }}>Convert</button>
            {results.steroid && <div className="alert alert-success mt-2 mb-0">Equivalent: {String(results.steroid.equivalent_dose_mg)} mg {String(results.steroid.to)}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
