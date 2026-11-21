import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, LabResult, PatientDetail, TimelineData, VisitDetail } from '../api/client';
import { latestLabRows } from '../utils/labResults';
import OldReportsPanel from '../components/OldReportsPanel';
import PcosScoringPanel from '../components/PcosScoringPanel';
import SuggestField from '../components/SuggestField';
import ThyroidScoringPanel from '../components/ThyroidScoringPanel';
import { clearVisitDraft, draftKey, loadVisitDraft, saveVisitDraft } from '../utils/draftStorage';
import { mergePcosScoresIntoExamination } from '../utils/pcosExamination';
import { mergeThyroidScoresIntoExamination } from '../utils/thyroidExamination';
import { rememberTyped } from '../utils/typedMemory';
import { followUpNotesForDisplay } from '../utils/followUpNotes';

type TemplateField = {
  key: string;
  label: string;
  multiline?: boolean;
  group?: string;
  group_label?: string;
};

function minFollowUpDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

function parsePatientAge(age: string): number | null {
  const m = age.trim().match(/(\d+(?:\.\d+)?)/);
  return m ? Number(m[1]) : null;
}

function calcBmi(heightCm: string, weightKg: string): string {
  const h = Number(heightCm);
  const w = Number(weightKg);
  if (!h || !w) return '';
  return (w / ((h / 100) ** 2)).toFixed(2);
}

function calcEgfrLocal(creatinine: number, age: number, sex: string): number {
  const female = sex.toLowerCase().startsWith('f');
  const k = female ? 0.7 : 0.9;
  const alpha = female ? -0.329 : -0.411;
  let egfr = 141 * Math.min(creatinine / k, 1) ** alpha
    * Math.max(creatinine / k, 1) ** -1.209
    * 0.993 ** age;
  if (female) egfr *= 1.018;
  return Math.round(egfr * 10) / 10;
}

type PriorVitals = {
  date: string;
  height: number | null;
  weight: number | null;
  bmi: number | null;
};

function isFollowUpVisitType(visitType: string) {
  return visitType === 'Follow-up' || visitType === 'Revisit';
}

function formatVitalDate(isoDate: string) {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function formatDelta(current: string, previous: number | null, unit: string) {
  const value = Number(current);
  if (!current || previous == null || Number.isNaN(value)) return null;
  const delta = value - previous;
  if (Math.abs(delta) < 0.05) return `Same as last (${previous} ${unit})`;
  const sign = delta > 0 ? '+' : '';
  return `${sign}${delta.toFixed(1)} ${unit} vs last (${previous} ${unit})`;
}

function noteMacros(): { title: string; text: string }[] {
  try {
    const parsed = JSON.parse(localStorage.getItem('endo-note-macros') || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function VisitForm() {
  const { patientId, id: editVisitId } = useParams<{ patientId?: string; id?: string }>();
  const isEdit = Boolean(editVisitId);
  const navigate = useNavigate();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [chartLabs, setChartLabs] = useState<LabResult[]>([]);
  const [visitMeta, setVisitMeta] = useState<VisitDetail | null>(null);
  const [templateOptions, setTemplateOptions] = useState<{ id: string; label: string }[]>([]);
  const [templateFields, setTemplateFields] = useState<TemplateField[]>([]);
  const [form, setForm] = useState({
    visit_type: 'New Visit',
    chief_complaints: '',
    height: '', weight: '', bp_systolic: '', bp_diastolic: '',
    pulse: '', temperature: '', spo2: '',
    history: '', examination: '', diagnosis: '', investigation: '', ordered_investigations: '',
    comorbidities: '', follow_up_date: '', follow_up_notes: '',
    specialty_template: '', mid_parental_height: '',
  });
  const [specialtyData, setSpecialtyData] = useState<Record<string, string>>({});
  const [macroTick, setMacroTick] = useState(0);
  const [suggestedTemplate, setSuggestedTemplate] = useState<string | null>(null);
  const [templateTouched, setTemplateTouched] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [autosaveMsg, setAutosaveMsg] = useState('');
  const [preventForm, setPreventForm] = useState({
    age: '', total_cholesterol: '', hdl_cholesterol: '', sbp: '',
    on_antihypertensive: false, diabetes: false, smoker: false,
    egfr: '', bmi: '', on_statin: false,
  });
  const [preventResult, setPreventResult] = useState<Record<string, unknown> | null>(null);
  const [priorVitals, setPriorVitals] = useState<PriorVitals | null>(null);
  const [oldReportsOpen, setOldReportsOpen] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const creatingDraftRef = useRef(false);

  const loadPriorVitals = useCallback((timeline: TimelineData, excludeDate?: string | null) => {
    const prior = [...timeline.vitals]
      .filter(v => v.date !== excludeDate && (v.height != null || v.weight != null))
      .reverse()
      .find(Boolean);
    setPriorVitals(prior ?? null);
  }, []);

  useEffect(() => {
    api.templateOptions().then(setTemplateOptions).catch(() => {});
  }, []);

  useEffect(() => {
    const pid = patient?.id || (patientId ? Number(patientId) : 0);
    if (!pid) return;
    api.labs(pid).then(setChartLabs).catch(() => setChartLabs([]));
  }, [patient?.id, patientId]);

  useEffect(() => {
    if (isEdit && editVisitId) {
      api.visit(Number(editVisitId)).then(v => {
        if (v.status === 'locked') {
          navigate(`/visits/${v.id}`);
          return;
        }
        setVisitMeta(v);
        setForm({
          visit_type: v.visit_type,
          chief_complaints: v.chief_complaints || '',
          height: v.height != null ? String(v.height) : '',
          weight: v.weight != null ? String(v.weight) : '',
          bp_systolic: v.bp_systolic != null ? String(v.bp_systolic) : '',
          bp_diastolic: v.bp_diastolic != null ? String(v.bp_diastolic) : '',
          pulse: v.pulse != null ? String(v.pulse) : '',
          temperature: v.temperature != null ? String(v.temperature) : '',
          spo2: v.spo2 != null ? String(v.spo2) : '',
          history: v.history || '',
          examination: v.examination || '',
          diagnosis: v.diagnosis || '',
          investigation: v.investigation || '',
          ordered_investigations: v.ordered_investigations || '',
          comorbidities: v.comorbidities || '',
          follow_up_date: v.follow_up_date ? v.follow_up_date.slice(0, 10) : '',
          follow_up_notes: followUpNotesForDisplay(v.follow_up_notes, v.follow_up_date),
          specialty_template: v.specialty_template || '',
          mid_parental_height: v.mid_parental_height != null ? String(v.mid_parental_height) : '',
        });
        if (v.specialty_data) {
          try {
            const parsed = JSON.parse(v.specialty_data);
            const { condition: _, ...rest } = parsed;
            setSpecialtyData(rest);
          } catch { /* ignore */ }
        }
        api.patient(v.patient_id).then(setPatient);
        api.timeline(v.patient_id).then(t => loadPriorVitals(t, v.visit_date.slice(0, 10)));
        if (v.prevent_data) {
          const pd = v.prevent_data as { inputs?: typeof preventForm; results?: Record<string, unknown> };
          if (pd.inputs) setPreventForm(prev => ({ ...prev, ...pd.inputs }));
          if (pd.results) setPreventResult(pd.results);
        }
      });
    } else if (patientId) {
      api.patient(Number(patientId)).then(async p => {
        setPatient(p);
        const age = parsePatientAge(p.age);
        if (age != null) setPreventForm(f => ({ ...f, age: String(Math.min(79, Math.max(30, Math.round(age)))) }));
        if (p.visits.length > 0) {
          setForm(f => ({ ...f, visit_type: 'Revisit' }));
        }
        const local = loadVisitDraft(draftKey(patientId));
        if (local?.form) {
          setForm(f => ({ ...f, ...local.form }));
          if (local.specialtyData) setSpecialtyData(local.specialtyData);
          if (local.preventForm) setPreventForm(prev => ({ ...prev, ...local.preventForm as typeof prev }));
          if (local.preventResult !== undefined) setPreventResult(local.preventResult ?? null);
          setAutosaveMsg(`Offline draft restored (${new Date(local.savedAt).toLocaleTimeString()})`);
          setDraftRestored(true);
        }
        try {
          const qv = await api.queueVitals(Number(patientId)).catch(() => api.appointmentVitals(Number(patientId)));
          const vitalsPatch = {
            height: qv.height != null ? String(qv.height) : '',
            weight: qv.weight != null ? String(qv.weight) : '',
            bp_systolic: qv.bp_systolic != null ? String(qv.bp_systolic) : '',
            bp_diastolic: qv.bp_diastolic != null ? String(qv.bp_diastolic) : '',
            pulse: qv.pulse != null ? String(qv.pulse) : '',
            temperature: qv.temperature != null ? String(qv.temperature) : '',
            spo2: qv.spo2 != null ? String(qv.spo2) : '',
          };
          setForm(f => ({
            ...f,
            height: f.height || vitalsPatch.height,
            weight: f.weight || vitalsPatch.weight,
            bp_systolic: f.bp_systolic || vitalsPatch.bp_systolic,
            bp_diastolic: f.bp_diastolic || vitalsPatch.bp_diastolic,
            pulse: f.pulse || vitalsPatch.pulse,
            temperature: f.temperature || vitalsPatch.temperature,
            spo2: f.spo2 || vitalsPatch.spo2,
          }));
        } catch { /* no queue vitals */ }
      });
      api.timeline(Number(patientId)).then(t => loadPriorVitals(t)).catch(() => setPriorVitals(null));
    }
  }, [isEdit, editVisitId, patientId, navigate, loadPriorVitals]);

  useEffect(() => {
    if (!isEdit || !editVisitId || !patient || draftRestored) return;
    const local = loadVisitDraft(draftKey(patient.id, editVisitId));
    if (!local?.form) return;
    const serverTs = visitMeta?.draft_updated_at ? Date.parse(visitMeta.draft_updated_at) : 0;
    const localTs = Date.parse(local.savedAt);
    if (localTs > serverTs) {
      setForm(f => ({ ...f, ...local.form }));
      if (local.specialtyData) setSpecialtyData(local.specialtyData);
      setAutosaveMsg('Recovered newer offline draft');
      setDirty(true);
    }
    setDraftRestored(true);
  }, [isEdit, editVisitId, patient, visitMeta, draftRestored]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target as HTMLElement)?.isContentEditable) {
        if (e.key !== 'Escape') return;
      }
      if ((e.key === 'o' || e.key === 'O') && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (patient && patient.visits.length > 0) {
          e.preventDefault();
          setOldReportsOpen(v => !v);
        }
      }
      if (e.key === 'Escape' && oldReportsOpen) setOldReportsOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [patient, oldReportsOpen]);

  const computedBmi = useMemo(() => calcBmi(form.height, form.weight), [form.height, form.weight]);
  const patientAge = useMemo(() => (patient ? parsePatientAge(patient.age) : null), [patient]);
  const isPediatric = patientAge != null && patientAge < 18;
  const showVitalTrends = isFollowUpVisitType(form.visit_type) && priorVitals != null;
  const heightDelta = showVitalTrends ? formatDelta(form.height, priorVitals.height, 'cm') : null;
  const weightDelta = showVitalTrends ? formatDelta(form.weight, priorVitals.weight, 'kg') : null;
  const bmiDelta = showVitalTrends && computedBmi && priorVitals.bmi != null
    ? formatDelta(computedBmi, priorVitals.bmi, 'BMI')
    : null;

  useEffect(() => {
    if (!patient) return;
    setPreventForm(f => ({
      ...f,
      bmi: f.bmi || computedBmi || f.bmi,
      sbp: f.sbp || form.bp_systolic || f.sbp,
      egfr: f.egfr || specialtyData.rft_egfr || f.egfr,
      total_cholesterol: f.total_cholesterol || specialtyData.lipid_tchol || f.total_cholesterol,
      hdl_cholesterol: f.hdl_cholesterol || specialtyData.lipid_hdl || f.hdl_cholesterol,
      diabetes: f.diabetes || /diabetes|dm\b/i.test(form.diagnosis) || form.specialty_template === 'diabetes',
    }));
  }, [patient, computedBmi, form.bp_systolic, form.diagnosis, form.specialty_template, specialtyData]);

  useEffect(() => {
    if (!form.specialty_template) {
      setTemplateFields([]);
      return;
    }
    api.specialtyTemplates().then(all => {
      setTemplateFields(all[form.specialty_template] || []);
    }).catch(() => setTemplateFields([]));
  }, [form.specialty_template]);

  useEffect(() => {
    if (!form.diagnosis.trim() || templateTouched || isEdit) return;
    const timer = setTimeout(() => {
      api.suggestTemplate(form.diagnosis).then(res => {
        setSuggestedTemplate(res.template);
        if (res.template && !form.specialty_template) {
          setForm(f => ({ ...f, specialty_template: res.template! }));
        }
      }).catch(() => {});
    }, 400);
    return () => clearTimeout(timer);
  }, [form.diagnosis, templateTouched, form.specialty_template, isEdit]);

  useEffect(() => {
    if (!patient) return;
    const cr = specialtyData.rft_creatinine?.trim();
    const age = parsePatientAge(patient.age);
    if (!cr || age == null) return;
    const creatinine = Number(cr);
    if (!creatinine || creatinine <= 0) return;
    const egfr = String(calcEgfrLocal(creatinine, age, patient.sex));
    setSpecialtyData(prev => (prev.rft_egfr === egfr ? prev : { ...prev, rft_egfr: egfr }));
  }, [specialtyData.rft_creatinine, patient]);

  const buildPayload = useCallback(() => {
    let examination = form.examination;
    if (form.specialty_template === 'pcos') {
      examination = mergePcosScoresIntoExamination(examination, specialtyData);
    }
    if (form.specialty_template === 'thyroid') {
      examination = mergeThyroidScoresIntoExamination(examination, specialtyData);
    }
    return {
      ...form,
      examination,
      height: form.height ? Number(form.height) : null,
      weight: form.weight ? Number(form.weight) : null,
      mid_parental_height: form.mid_parental_height ? Number(form.mid_parental_height) : null,
      bp_systolic: form.bp_systolic ? Number(form.bp_systolic) : null,
      bp_diastolic: form.bp_diastolic ? Number(form.bp_diastolic) : null,
      pulse: form.pulse ? Number(form.pulse) : null,
      temperature: form.temperature ? Number(form.temperature) : null,
      spo2: form.spo2 ? Number(form.spo2) : null,
      follow_up_date: form.follow_up_date || null,
      specialty_template: form.specialty_template || null,
      specialty_data: form.specialty_template
        ? { condition: form.specialty_template, ...specialtyData }
        : (specialtyData.family_history || specialtyData.consent_note ? {
          family_history: specialtyData.family_history || '',
          consent_note: specialtyData.consent_note || '',
        } : null),
      prevent_data: { inputs: preventForm, results: preventResult },
    };
  }, [form, specialtyData, preventForm, preventResult]);

  // Always mirror draft to localStorage (offline-tolerant).
  useEffect(() => {
    if (!dirty || !patient) return;
    const key = isEdit && editVisitId ? draftKey(patient.id, editVisitId) : draftKey(patient.id);
    saveVisitDraft(key, {
      form,
      specialtyData,
      preventForm,
      preventResult,
    });
  }, [dirty, patient, isEdit, editVisitId, form, specialtyData, preventForm, preventResult]);

  // Server autosave for existing drafts.
  useEffect(() => {
    if (!isEdit || !editVisitId || !dirty || !patient) return;
    const timer = setTimeout(async () => {
      try {
        const payload = buildPayload();
        await api.updateVisit(Number(editVisitId), payload, true);
        setForm(f => (f.examination !== payload.examination ? { ...f, examination: payload.examination } : f));
        clearVisitDraft(draftKey(patient.id, editVisitId));
        clearVisitDraft(draftKey(patient.id));
        setAutosaveMsg(`Draft saved ${new Date().toLocaleTimeString()}`);
        setDirty(false);
      } catch {
        setAutosaveMsg('Offline — draft kept on this device');
      }
    }, 2500);
    return () => clearTimeout(timer);
  }, [isEdit, editVisitId, dirty, buildPayload, patient]);

  // Create-flow: promote to a server draft visit so work is not lost.
  useEffect(() => {
    if (isEdit || !patientId || !dirty || !patient || creatingDraftRef.current) return;
    const hasContent = Boolean(
      form.chief_complaints.trim()
      || form.diagnosis.trim()
      || form.history.trim()
      || form.examination.trim()
      || form.investigation.trim()
      || form.height
      || form.weight,
    );
    if (!hasContent) return;
    const timer = setTimeout(async () => {
      if (creatingDraftRef.current) return;
      creatingDraftRef.current = true;
      try {
        const payload = buildPayload();
        const visit = await api.createVisit(Number(patientId), payload);
        clearVisitDraft(draftKey(patientId));
        setAutosaveMsg('Draft visit created');
        navigate(`/visits/${visit.id}/edit`, { replace: true });
      } catch {
        creatingDraftRef.current = false;
        setAutosaveMsg('Offline — draft kept on this device');
      }
    }, 2800);
    return () => clearTimeout(timer);
  }, [isEdit, patientId, dirty, patient, form, buildPayload, navigate]);

  const markDirty = () => setDirty(true);

  const handleFollowUpDateChange = (followUpDate: string) => {
    if (followUpDate) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const selected = new Date(`${followUpDate}T12:00:00`);
      if (selected <= today) {
        setError('Follow-up date must be a future date.');
        return;
      }
    }
    setError('');
    setForm(prev => ({
      ...prev,
      follow_up_date: followUpDate,
      follow_up_notes: followUpNotesForDisplay(prev.follow_up_notes, followUpDate || prev.follow_up_date),
    }));
    markDirty();
  };

  const handleTemplateChange = (template: string) => {
    setTemplateTouched(true);
    setForm({ ...form, specialty_template: template });
    markDirty();
    if (!template) {
      setSpecialtyData(current => ({
        family_history: current.family_history || '',
        consent_note: current.consent_note || '',
      }));
    }
  };

  const fieldGroups = useMemo(() => {
    const map = new Map<string, TemplateField[]>();
    templateFields.forEach(f => {
      const g = f.group_label || 'Other';
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push(f);
    });
    return [...map.entries()];
  }, [templateFields]);

  const renderField = (f: TemplateField) => {
    const isAutoEgfr = f.key === 'rft_egfr';
    return (
      <div className={f.multiline ? 'col-12 mb-2' : 'col-md-4 col-lg-3 mb-2'} key={f.key}>
        <label className="form-label small mb-1">{f.label}</label>
        {isAutoEgfr ? (
          <input className="form-control form-control-sm" value={specialtyData[f.key] || ''} readOnly />
        ) : (
          <SuggestField
            field={`specialty_${f.key}`}
            multiline={Boolean(f.multiline)}
            rows={2}
            className="form-control form-control-sm"
            value={specialtyData[f.key] || ''}
            onChange={v => { setSpecialtyData({ ...specialtyData, [f.key]: v }); markDirty(); }}
          />
        )}
        {isAutoEgfr && (
          <div className="form-text">Auto-calculated from creatinine (CKD-EPI)</div>
        )}
        {latestLabRows(chartLabs).filter(lab => lab.test_name.trim().toLowerCase() === f.label.trim().toLowerCase()).map(lab => (
          <div className="form-text" key={lab.id}>On the chart: {lab.value} {lab.unit || ''} ({lab.result_date.slice(0, 10)})</div>
        ))}
      </div>
    );
  };

  const runPreventCalc = async () => {
    const age = Number(preventForm.age);
    if (!age || age < 30 || age > 79) {
      setError('PREVENT model requires age 30–79 years.');
      return;
    }
    setError('');
    const bmiVal = preventForm.bmi ? Number(preventForm.bmi) : (computedBmi ?? null);
    const egfrVal = preventForm.egfr ? Number(preventForm.egfr) : (specialtyData.rft_egfr ? Number(specialtyData.rft_egfr) : null);
    try {
      const r = await api.calcPreventAscvd({
        age,
        sex: patient?.sex || 'Male',
        total_cholesterol: Number(preventForm.total_cholesterol),
        hdl_cholesterol: Number(preventForm.hdl_cholesterol),
        sbp: Number(preventForm.sbp),
        on_antihypertensive: preventForm.on_antihypertensive,
        diabetes: preventForm.diabetes,
        smoker: preventForm.smoker,
        on_statin: preventForm.on_statin,
        egfr: egfrVal,
        bmi: bmiVal,
      });
      setPreventResult(r);
      markDirty();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PREVENT calculation failed');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = buildPayload();
      [
        'diagnosis',
        'chief_complaints',
        'history',
        'examination',
        'comorbidities',
        'investigation',
        'ordered_investigations',
        'follow_up_notes',
      ].forEach(field => rememberTyped(field, String((payload as Record<string, unknown>)[field] || '')));
      Object.entries(specialtyData).forEach(([key, val]) => {
        if (val && String(val).trim().length >= 2) rememberTyped(`specialty_${key}`, String(val));
      });
      if (isEdit && editVisitId) {
        await api.updateVisit(Number(editVisitId), payload);
        if (patient) {
          clearVisitDraft(draftKey(patient.id, editVisitId));
          clearVisitDraft(draftKey(patient.id));
        }
        navigate(`/visits/${editVisitId}`);
      } else {
        const visit = await api.createVisit(Number(patientId), payload);
        clearVisitDraft(draftKey(Number(patientId)));
        navigate(`/visits/${visit.id}/edit`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save visit');
    } finally {
      setLoading(false);
    }
  };

  const priorVisitCount = useMemo(() => {
    if (!patient) return 0;
    return patient.visits.filter(v => v.id !== Number(editVisitId || 0)).length;
  }, [patient, editVisitId]);

  const copyFromOldReport = useCallback((fields: {
    diagnosis?: string;
    chief_complaints?: string;
    history?: string;
    examination?: string;
    investigation?: string;
    comorbidities?: string;
  }) => {
    setForm(prev => ({
      ...prev,
      ...(fields.diagnosis != null ? { diagnosis: fields.diagnosis } : {}),
      ...(fields.chief_complaints != null ? { chief_complaints: fields.chief_complaints } : {}),
      ...(fields.history != null ? { history: fields.history } : {}),
      ...(fields.examination != null ? { examination: fields.examination } : {}),
      ...(fields.investigation != null ? { investigation: fields.investigation } : {}),
      ...(fields.comorbidities != null ? { comorbidities: fields.comorbidities } : {}),
    }));
    setDirty(true);
  }, []);

  if (!patient) return <div className="text-center py-5 text-muted">Loading patient…</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{isEdit ? 'Edit Case Sheet' : priorVisitCount > 0 ? 'Revisit' : 'New Visit'}</h2>
          <p className="page-subtitle">
            {patient.name}
            {patient.mrd_number ? ` · MRD ${patient.mrd_number}` : ''}
            {patient.age ? ` · ${patient.age}` : ''}
            {patient.sex ? ` · ${patient.sex}` : ''}
          </p>
        </div>
        <div className="d-flex align-items-center gap-2 flex-wrap">
          {priorVisitCount > 0 && (
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={() => setOldReportsOpen(true)}
            >
              <i className="fas fa-folder-open me-2"></i>Old Reports
              <span className="badge badge-soft ms-2">{priorVisitCount}</span>
            </button>
          )}
          <div className="text-end">
          {(isEdit || autosaveMsg) && (
            <span className="badge bg-warning text-dark me-2">Draft</span>
          )}
          {autosaveMsg && <small className="text-muted d-block">{autosaveMsg}</small>}
          {priorVisitCount > 0 && (
            <small className="text-muted d-block mt-1">Press <kbd>O</kbd> for Old Reports</small>
          )}
        </div>
        </div>
      </div>
      {(patient.allergies?.trim() || patient.problem_list?.trim()) && (
        <div className="alert alert-danger">
          <strong>Clinical alerts —</strong>
          {patient.allergies?.trim() && <span className="ms-2">Allergies: {patient.allergies}</span>}
          {patient.problem_list?.trim() && <span className="ms-2">Problem list: {patient.problem_list}</span>}
        </div>
      )}
      {error && <div className="alert alert-danger">{error}</div>}
      {priorVisitCount > 0 && (
        <div className="alert alert-info py-2 small d-flex align-items-center justify-content-between gap-2">
          <span>
            <i className="fas fa-info-circle me-1"></i>
            Review previous visits, prescriptions, labs, and imaging without leaving this page.
          </span>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setOldReportsOpen(true)}>
            Open Old Reports
          </button>
        </div>
      )}
      <div className="card p-4">
        <form onSubmit={handleSubmit}>
          <div className="row">
            <div className="col-md-4 mb-3">
              <label className="form-label">Visit Type</label>
              <select className="form-select" value={form.visit_type}
                onChange={e => { setForm({ ...form, visit_type: e.target.value }); markDirty(); }}>
                <option>New Visit</option>
                <option>Revisit</option>
                <option>Follow-up</option>
                <option>Emergency</option>
              </select>
            </div>
            <div className="col-md-8 mb-3">
              <label className="form-label">Diagnosis</label>
              <SuggestField
                field="diagnosis"
                value={form.diagnosis}
                onChange={v => { setForm({ ...form, diagnosis: v }); markDirty(); }}
                placeholder="Start typing — suggestions from your clinic"
              />
              {!isEdit && suggestedTemplate && form.specialty_template !== suggestedTemplate && (
                <div className="form-text">
                  Suggested: <strong className="text-capitalize">{suggestedTemplate}</strong>
                  <button type="button" className="btn btn-link btn-sm p-0 ms-2" onClick={() => {
                    setForm({ ...form, specialty_template: suggestedTemplate! });
                    markDirty();
                  }}>Apply</button>
                </div>
              )}
            </div>
            <div className="col-md-4 mb-3">
              <label className="form-label">Specialty Template</label>
              <select className="form-select" value={form.specialty_template}
                onChange={e => handleTemplateChange(e.target.value)}>
                <option value="">None</option>
                {templateOptions.map(t => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="col-md-6 mb-3">
              <label className="form-label">Family history</label>
              <textarea className="form-control" rows={2} value={specialtyData.family_history || ''}
                onChange={e => { setSpecialtyData(current => ({ ...current, family_history: e.target.value })); markDirty(); }} />
            </div>
            <div className="col-md-6 mb-3">
              <label className="form-label">Consent note</label>
              <textarea className="form-control" rows={2} placeholder="What the patient agreed to have recorded" value={specialtyData.consent_note || ''}
                onChange={e => { setSpecialtyData(current => ({ ...current, consent_note: e.target.value })); markDirty(); }} />
            </div>
            <div className="col-12 mb-3">
              <label className="form-label">Chief Complaints</label>
              <div className="d-flex gap-2 mb-1">
                <select className="form-select form-select-sm" defaultValue="" onChange={e => {
                  const text = e.target.value;
                  e.target.value = '';
                  if (!text) return;
                  setForm(current => ({ ...current, chief_complaints: [current.chief_complaints, text].filter(Boolean).join('\n') }));
                  markDirty();
                }}>
                  <option value="">Insert a saved note…</option>
                  {noteMacros().map(item => <option key={`${macroTick}-${item.title}`} value={item.text}>{item.title}</option>)}
                </select>
                <button type="button" className="btn btn-sm btn-outline-secondary text-nowrap" onClick={() => {
                  const title = window.prompt('Name this note');
                  const text = form.chief_complaints.trim();
                  if (!title || !text) return;
                  const next = [...noteMacros(), { title, text }];
                  localStorage.setItem('endo-note-macros', JSON.stringify(next));
                  setMacroTick(n => n + 1);
                }}>Save note</button>
              </div>
              <SuggestField
                field="chief_complaints"
                multiline
                rows={2}
                value={form.chief_complaints}
                onChange={v => { setForm({ ...form, chief_complaints: v }); markDirty(); }}
              />
            </div>
            <div className="col-12 mb-2">
              <h6 className="text-muted mb-0">Vitals <span className="fw-normal">(optional)</span></h6>
            </div>
            {showVitalTrends && (
              <div className="col-12 mb-2">
                <div className="alert alert-info py-2 small mb-0">
                  <i className="fas fa-chart-line me-1"></i>
                  <strong>Previous visit ({formatVitalDate(priorVitals.date)}):</strong>{' '}
                  {priorVitals.height != null && <>Height {priorVitals.height} cm · </>}
                  {priorVitals.weight != null && <>Weight {priorVitals.weight} kg · </>}
                  {priorVitals.bmi != null && <>BMI {priorVitals.bmi}</>}
                  {priorVitals.height == null && priorVitals.weight == null && 'No height/weight recorded'}
                  <span className="text-muted ms-1">— enter today&apos;s values below to see trend</span>
                </div>
              </div>
            )}
            {['height', 'weight', 'bp_systolic', 'bp_diastolic', 'pulse', 'temperature', 'spo2'].map(f => (
              <div className="col-md-3 mb-3" key={f}>
                <label className="form-label text-capitalize">{f.replace('_', ' ')}</label>
                <input type="number" step="any" className="form-control"
                  value={form[f as keyof typeof form]}
                  onChange={e => { setForm({ ...form, [f]: e.target.value }); markDirty(); }} />
                {f === 'height' && heightDelta && (
                  <div className="form-text text-primary">{heightDelta}</div>
                )}
                {f === 'weight' && weightDelta && (
                  <div className="form-text text-primary">{weightDelta}</div>
                )}
              </div>
            ))}
            <div className="col-md-3 mb-3">
              <label className="form-label">BMI</label>
              <input className="form-control bg-light" readOnly value={computedBmi}
                placeholder="Auto from height & weight" />
              {bmiDelta && <div className="form-text text-primary">{bmiDelta}</div>}
            </div>
            {isPediatric && (
              <div className="col-md-3 mb-3">
                <label className="form-label">Mid-parental Height (cm)</label>
                <input type="number" step="any" className="form-control"
                  value={form.mid_parental_height}
                  onChange={e => { setForm({ ...form, mid_parental_height: e.target.value }); markDirty(); }} />
                <div className="form-text">Plotted on growth chart (age &lt; 18)</div>
              </div>
            )}
            <div className="col-12 mb-3">
              <div className="card bg-light p-3">
                <h6 className="mb-2"><i className="fas fa-heart me-1"></i>PREVENT ASCVD Calculator</h6>
                <p className="small text-muted mb-2">AHA PREVENT model (ages 30–79). Prefilled from vitals and labs where available.</p>
                <div className="row g-2">
                  {[
                    { key: 'age', label: 'Age (years)' },
                    { key: 'total_cholesterol', label: 'Total cholesterol (mg/dL)' },
                    { key: 'hdl_cholesterol', label: 'HDL (mg/dL)' },
                    { key: 'sbp', label: 'SBP (mmHg)' },
                    { key: 'egfr', label: 'eGFR (optional)' },
                    { key: 'bmi', label: 'BMI (optional)' },
                  ].map(f => (
                    <div className="col-md-4" key={f.key}>
                      <label className="form-label small">{f.label}</label>
                      <input className="form-control form-control-sm" type="number" step="any"
                        value={preventForm[f.key as keyof typeof preventForm] as string}
                        onChange={e => { setPreventForm({ ...preventForm, [f.key]: e.target.value }); markDirty(); }} />
                    </div>
                  ))}
                  {[
                    { key: 'on_antihypertensive', label: 'On BP medication' },
                    { key: 'diabetes', label: 'Diabetes' },
                    { key: 'smoker', label: 'Current smoker' },
                    { key: 'on_statin', label: 'On statin' },
                  ].map(f => (
                    <div className="col-md-3" key={f.key}>
                      <div className="form-check mt-4">
                        <input className="form-check-input" type="checkbox" id={`pf-${f.key}`}
                          checked={preventForm[f.key as keyof typeof preventForm] as boolean}
                          onChange={e => { setPreventForm({ ...preventForm, [f.key]: e.target.checked }); markDirty(); }} />
                        <label className="form-check-label small" htmlFor={`pf-${f.key}`}>{f.label}</label>
                      </div>
                    </div>
                  ))}
                </div>
                <button type="button" className="btn btn-sm btn-primary mt-2" onClick={runPreventCalc}>
                  Calculate PREVENT Risk
                </button>
                {preventResult && (
                  <div className="alert alert-info mt-2 mb-0 small">
                    <strong>10-yr ASCVD:</strong> {String(preventResult.ascvd_risk_10y)}% ·{' '}
                    <strong>30-yr ASCVD:</strong>{' '}
                    {preventResult.ascvd_risk_30y != null ? `${preventResult.ascvd_risk_30y}%` : 'N/A (age >59)'} ·{' '}
                    <strong>10-yr Total CVD:</strong> {String(preventResult.total_cvd_risk_10y)}% ·{' '}
                    <strong>Category:</strong> {String(preventResult.risk_category)}
                  </div>
                )}
              </div>
            </div>
            {form.specialty_template === 'pcos' && (
              <div className="col-12 mb-3">
                <PcosScoringPanel
                  data={specialtyData}
                  onChange={next => { setSpecialtyData(next); markDirty(); }}
                />
              </div>
            )}
            {form.specialty_template === 'thyroid' && (
              <div className="col-12 mb-3">
                <ThyroidScoringPanel
                  data={specialtyData}
                  onChange={next => { setSpecialtyData(next); markDirty(); }}
                />
              </div>
            )}
            {fieldGroups.map(([groupLabel, fields]) => (
              <div className="col-12 mb-3" key={groupLabel}>
                <div className="card bg-light p-3">
                  <h6 className="mb-2">{groupLabel}</h6>
                  <div className="row">{fields.map(renderField)}</div>
                </div>
              </div>
            ))}
            {[
              { key: 'history', label: 'History' },
              { key: 'examination', label: 'Examination' },
              { key: 'comorbidities', label: 'Comorbidities' },
            ].map(f => (
              <div className="col-12 mb-3" key={f.key}>
                <label className="form-label">{f.label}</label>
                <SuggestField
                  field={f.key}
                  multiline
                  rows={2}
                  value={String(form[f.key as keyof typeof form] || '')}
                  onChange={v => { setForm({ ...form, [f.key]: v }); markDirty(); }}
                />
                {f.key === 'examination' && (form.specialty_template === 'pcos' || form.specialty_template === 'thyroid') && (
                  <div className="form-text">
                    {form.specialty_template === 'pcos' && 'Ferriman-Gallwey and Ludwig scores are appended here automatically when you save.'}
                    {form.specialty_template === 'thyroid' && 'WHO goitre, CAS, and TED severity grades are appended here automatically when you save.'}
                  </div>
                )}
              </div>
            ))}
            <div className="col-12 mb-3">
              <label className="form-label">Current Investigations</label>
              <SuggestField
                field="investigation"
                multiline
                rows={2}
                value={form.investigation}
                onChange={v => { setForm({ ...form, investigation: v }); markDirty(); }}
              />
              <div className="form-text">A line such as HbA1c 7.2 is saved with the other results. These lines are not sent to billing.</div>
              {latestLabRows(chartLabs).length > 0 && (
                <div className="form-text">
                  On the chart: {latestLabRows(chartLabs).map(lab => `${lab.test_name} ${lab.value}${lab.unit ? ` ${lab.unit}` : ''}`).join(' · ')}
                </div>
              )}
            </div>
            <div className="col-12 mb-3">
              <label className="form-label">Ordered investigations</label>
              <SuggestField
                field="ordered_investigations"
                multiline
                rows={2}
                value={form.ordered_investigations}
                placeholder={'One test per line, for example:\nHbA1c\nTSH\nLipid profile'}
                onChange={v => { setForm({ ...form, ordered_investigations: v }); markDirty(); }}
              />
              <div className="form-text">Billing sees each line as a separate test.</div>
            </div>
            <div className="col-12 mb-3">
              <label className="form-label">Follow-up</label>
              <SuggestField
                field="follow_up_notes"
                multiline
                rows={2}
                value={form.follow_up_notes}
                onChange={v => { setForm({ ...form, follow_up_notes: v }); markDirty(); }}
              />
            </div>
            <div className="col-md-6 mb-3">
              <label className="form-label">Schedule Follow-up Visit</label>
              <input type="date" className="form-control" value={form.follow_up_date}
                min={minFollowUpDate()}
                onChange={e => handleFollowUpDateChange(e.target.value)} />
              <div className="form-text">Printed as Next Visit. Use the box above for any extra instruction.</div>
            </div>
          </div>
          <button type="submit" className="btn btn-primary me-2" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Save Case Sheet' : 'Create Visit'}
          </button>
          {isEdit && visitMeta && (
            <Link to={`/visits/${visitMeta.id}`} className="btn btn-outline-secondary">Back to Visit</Link>
          )}
          {!isEdit && (
            <Link to={`/patients/${patient.id}`} className="btn btn-outline-secondary">Back to Patient</Link>
          )}
        </form>
      </div>

      {priorVisitCount > 0 && !oldReportsOpen && (
        <button
          type="button"
          className="old-reports-fab"
          onClick={() => setOldReportsOpen(true)}
          aria-label="Open old reports"
        >
          <i className="fas fa-folder-open"></i>
          Old Reports
          <span className="fab-count">{priorVisitCount}</span>
        </button>
      )}

      <OldReportsPanel
        patientId={patient.id}
        patientName={patient.name}
        visits={patient.visits}
        excludeVisitId={editVisitId ? Number(editVisitId) : null}
        open={oldReportsOpen}
        onClose={() => setOldReportsOpen(false)}
        onCopyToForm={copyFromOldReport}
      />
    </div>
  );
}
