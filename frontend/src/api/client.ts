function normalizeApiBase(url: string): string {
  return url ? url.replace('://localhost', '://127.0.0.1') : '';
}

const API_BASE = normalizeApiBase(import.meta.env.VITE_API_URL || '');

export interface User {
  id: number;
  email: string | null;
  display_name: string | null;
  role: string;
  qualifications: string | null;
  kmc_number: string | null;
  doctor_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Patient {
  id: number;
  mrd_number: string | null;
  name: string;
  age: string;
  sex: string;
  contact: string | null;
  address: string | null;
  date_registered: string;
  doctor_id: number | null;
}

export interface VisitSummary {
  id: number;
  visit_date: string;
  visit_type: string;
  diagnosis: string | null;
  chief_complaints: string | null;
}

export interface PatientDetail extends Patient {
  visits: VisitSummary[];
}

export interface Prescription {
  id: number;
  visit_id: number;
  brand_medication_id: number;
  custom_drug_name: string | null;
  custom_generic_name: string | null;
  dosage: string | null;
  dose_morning: string | null;
  dose_afternoon: string | null;
  dose_evening: string | null;
  frequency: string | null;
  timing: string | null;
  duration: string | null;
  instructions: string | null;
  warnings: string | null;
  drug_name: string | null;
  generic_name: string | null;
  formatted_dosage: string | null;
}

export interface VisitDetail {
  id: number;
  patient_id: number;
  visit_date: string;
  visit_type: string;
  chief_complaints: string | null;
  height: number | null;
  weight: number | null;
  bmi: number | null;
  mid_parental_height?: number | null;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  pulse: number | null;
  temperature: number | null;
  spo2: number | null;
  history: string | null;
  examination: string | null;
  diagnosis: string | null;
  investigation: string | null;
  comorbidities: string | null;
  follow_up_date: string | null;
  follow_up_notes: string | null;
  specialty_template?: string | null;
  specialty_data?: string | null;
  pdf_page_count?: number | null;
  pdf_font_size?: number | null;
  pdf_header_space?: number | null;
  pdf_left_margin?: number | null;
  pdf_hide_patient_info?: boolean | null;
  pdf_hide_header?: boolean | null;
  prevent_data?: Record<string, unknown> | null;
  status?: string;
  draft_updated_at?: string | null;
  finalized_at?: string | null;
  patient_name: string | null;
  patient_mrd: string | null;
  prescriptions: Prescription[];
  warnings: { drug: string; comorbidity: string; type: string; severity: string | null; recommendation: string | null }[];
  specialty_fields?: { key: string; label: string; value: string }[];
  investigations_text?: string | null;
  can_finalize?: boolean;
}

export interface Diagnosis {
  id: number;
  diagnosis_name: string;
  category: string | null;
  icd_code: string | null;
}

export interface DrugSearchResult {
  type: string;
  id: number;
  generic_name: string;
  brand_id?: number;
  brand_name?: string;
  display_label?: string;
  is_insulin?: boolean;
  suggested_dosage?: string;
  strength?: string;
  formulation?: string;
}

export interface Brand {
  id: number;
  brand_name: string;
  display_label: string;
  is_insulin: boolean;
  suggested_dosage: string | null;
  strength: string | null;
  formulation: string | null;
}

export interface DashboardData {
  stats: {
    total_patients: number;
    total_visits: number;
    total_drugs: number;
    total_brands: number;
  };
  recent_visits: {
    id: number;
    visit_date: string;
    visit_type: string;
    diagnosis: string | null;
    chief_complaints: string | null;
    patient_id: number;
    patient_name: string;
    patient_mrd: string | null;
  }[];
}

export interface LabResult {
  id: number;
  patient_id: number;
  test_name: string;
  value: string;
  unit: string | null;
  reference_range: string | null;
  result_date: string;
  notes: string | null;
}

export interface ImagingResult {
  id: number;
  patient_id: number;
  study_type: string;
  findings: string | null;
  report_date: string;
}

export interface TimelineData {
  vitals: { date: string; weight: number | null; bmi: number | null; height: number | null; bp_systolic: number | null; bp_diastolic: number | null }[];
  labs: Record<string, { date: string; value: number | string; unit: string | null }[]>;
  visit_count: number;
}

export interface FollowUpItem {
  visit_id: number;
  patient_id: number;
  patient_name: string;
  patient_mrd: string | null;
  follow_up_date: string;
  diagnosis: string | null;
  days_overdue: number;
}

export interface CdsRecommendation {
  category: string;
  severity: string;
  source: string;
  recommendation: string;
}

export interface Appointment {
  id: number;
  patient_id: number;
  patient_name: string | null;
  scheduled_at: string;
  duration_minutes: number;
  status: string;
  notes: string | null;
}

export interface Bill {
  id: number;
  visit_id: number;
  patient_id: number;
  patient_name: string | null;
  description: string;
  amount: number;
  procedure_code: string | null;
  payment_status: string;
  payment_method: string | null;
}

export interface AnalyticsData {
  diagnosis_distribution: { diagnosis: string; count: number }[];
  visit_volume_by_month: { month: number; count: number }[];
  top_medications: { drug: string; count: number }[];
  revenue_summary: { total_billed: number; total_paid: number; pending: number };
}

export function getTokens() {
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  };
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

const REQUEST_TIMEOUT_MS = 15000;

async function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Request timed out — is the backend running? Start Start_Backend.bat first.');
    }
    throw new Error('Cannot reach API server. Start Start_Backend.bat, then try again.');
  } finally {
    clearTimeout(timer);
  }
}

export interface PdfLayout {
  font_size?: number;
  header_space?: number;
  left_margin?: number;
  hide_patient_info?: boolean;
  hide_header?: boolean;
}

function pdfLayoutParams(layout?: PdfLayout, download = false): URLSearchParams {
  const params = new URLSearchParams();
  if (download) params.set('download', 'true');
  if (layout?.font_size != null) params.set('font_size', String(layout.font_size));
  if (layout?.header_space != null) params.set('header_space', String(layout.header_space));
  if (layout?.left_margin != null) params.set('left_margin', String(layout.left_margin));
  if (layout?.hide_patient_info != null) {
    params.set('hide_patient_info', layout.hide_patient_info ? 'true' : 'false');
  }
  if (layout?.hide_header != null) {
    params.set('hide_header', layout.hide_header ? 'true' : 'false');
  }
  return params;
}

async function fetchWithAuth(path: string): Promise<Response> {
  const { access, refresh } = getTokens();
  const headers: Record<string, string> = {};
  if (access) headers['Authorization'] = `Bearer ${access}`;

  let res = await fetchWithTimeout(`${API_BASE}${path}`, { headers });
  if (res.status === 401 && refresh) {
    const refreshRes = await fetchWithTimeout(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (refreshRes.ok) {
      const tokens: TokenResponse = await refreshRes.json();
      setTokens(tokens.access_token, tokens.refresh_token);
      headers['Authorization'] = `Bearer ${tokens.access_token}`;
      res = await fetchWithTimeout(`${API_BASE}${path}`, { headers });
    }
  }
  return res;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { access, refresh } = getTokens();
  const headers: Record<string, string> = {
  ...(options.headers as Record<string, string> || {}),
  };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  if (access) headers['Authorization'] = `Bearer ${access}`;

  let res = await fetchWithTimeout(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && refresh) {
    const refreshRes = await fetchWithTimeout(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (refreshRes.ok) {
      const tokens: TokenResponse = await refreshRes.json();
      setTokens(tokens.access_token, tokens.refresh_token);
      headers['Authorization'] = `Bearer ${tokens.access_token}`;
      res = await fetchWithTimeout(`${API_BASE}${path}`, { ...options, headers });
    } else {
      clearTokens();
      window.location.href = '/login';
      throw new Error('Session expired');
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join(', ') : 'Request failed';
    throw new Error(message || 'Request failed');
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (data: { email: string; password: string; display_name: string; qualifications?: string; kmc_number?: string }) =>
    request<User>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request<User>('/api/v1/auth/me'),
  updateProfile: (data: { display_name: string; qualifications?: string; kmc_number?: string }) =>
    request<User>('/api/v1/auth/profile', { method: 'PATCH', body: JSON.stringify(data) }),
  dashboard: () => request<DashboardData>('/api/v1/dashboard'),
  patients: (q?: string, search_type?: string) =>
    request<Patient[]>(`/api/v1/patients?${new URLSearchParams({ ...(q ? { q } : {}), ...(search_type ? { search_type } : {}) })}`),
  patient: (id: number) => request<PatientDetail>(`/api/v1/patients/${id}`),
  createPatient: (data: Omit<Patient, 'id' | 'date_registered' | 'doctor_id'>) =>
    request<Patient>('/api/v1/patients', { method: 'POST', body: JSON.stringify(data) }),
  updatePatient: (id: number, data: Partial<Patient>) =>
    request<Patient>(`/api/v1/patients/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  createVisit: (patientId: number, data: Record<string, unknown>) =>
    request<VisitDetail>(`/api/v1/patients/${patientId}/visits`, { method: 'POST', body: JSON.stringify(data) }),
  updateVisit: (visitId: number, data: Record<string, unknown>, autosave = false) =>
    request<VisitDetail>(`/api/v1/visits/${visitId}?autosave=${autosave}`, { method: 'PATCH', body: JSON.stringify(data) }),
  finalizeVisit: (visitId: number) =>
    request<VisitDetail>(`/api/v1/visits/${visitId}/finalize`, { method: 'POST' }),
  visit: (id: number) => request<VisitDetail>(`/api/v1/visits/${id}`),
  addPrescription: (visitId: number, data: Record<string, unknown>) =>
    request<{ success: boolean; prescription_id: number; warnings: unknown[] }>(
      `/api/v1/visits/${visitId}/prescriptions`,
      { method: 'POST', body: JSON.stringify(data) },
    ),
  deletePrescription: (id: number) =>
    request<void>(`/api/v1/prescriptions/${id}`, { method: 'DELETE' }),
  searchDrugs: (q: string) => request<DrugSearchResult[]>(`/api/v1/medications/search?q=${encodeURIComponent(q)}`),
  getBrands: (genericId: number) => request<Brand[]>(`/api/v1/medications/brands/${genericId}`),
  diagnoses: () => request<Diagnosis[]>('/api/v1/diagnoses'),
  uploadMedications: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ generic_count: number; brand_count: number; removed_count: number }>(
      '/api/v1/medications/upload',
      { method: 'POST', body: fd, headers: {} },
    );
  },
  uploadDiagnoses: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ count: number }>('/api/v1/diagnoses/upload', { method: 'POST', body: fd, headers: {} });
  },
  pdfUrl: (visitId: number, layout?: PdfLayout, download = false) => {
    const params = pdfLayoutParams(layout, download);
    return `${API_BASE}/api/v1/visits/${visitId}/prescription/pdf?${params}`;
  },
  fetchPrescriptionPdf: async (visitId: number, layout?: PdfLayout, download = false) => {
    const params = pdfLayoutParams(layout, download);
    const res = await fetchWithAuth(`/api/v1/visits/${visitId}/prescription/pdf?${params}`);
    if (!res.ok) throw new Error('Failed to load PDF');
    return res.blob();
  },
  fetchPrescriptionHtml: async (visitId: number, layout?: PdfLayout) => {
    const params = pdfLayoutParams(layout);
    const res = await fetchWithAuth(`/api/v1/visits/${visitId}/prescription/preview?${params}`);
    if (!res.ok) throw new Error('Failed to load preview');
    return res.text();
  },
  labs: (patientId: number) => request<LabResult[]>(`/api/v1/patients/${patientId}/labs`),
  addLab: (patientId: number, data: Record<string, unknown>) =>
    request<LabResult>(`/api/v1/patients/${patientId}/labs`, { method: 'POST', body: JSON.stringify(data) }),
  deleteLab: (labId: number) => request<void>(`/api/v1/labs/${labId}`, { method: 'DELETE' }),
  imaging: (patientId: number) => request<ImagingResult[]>(`/api/v1/patients/${patientId}/imaging`),
  addImaging: (patientId: number, data: Record<string, unknown>) =>
    request<ImagingResult>(`/api/v1/patients/${patientId}/imaging`, { method: 'POST', body: JSON.stringify(data) }),
  timeline: (patientId: number) => request<TimelineData>(`/api/v1/patients/${patientId}/timeline`),
  followUps: () => request<FollowUpItem[]>('/api/v1/follow-ups'),
  visitCds: (visitId: number) => request<CdsRecommendation[]>(`/api/v1/visits/${visitId}/cds`),
  diabetesDashboard: (patientId: number) => request<{
    hba1c_trend: { date: string; value: string; unit: string | null }[];
    cgm_readings: { time: string; glucose: number }[];
    insulin_dosing: { visit_date: string; drug: string; morning: string | null; afternoon: string | null; evening: string | null }[];
  }>(`/api/v1/patients/${patientId}/diabetes-dashboard`),
  growthChart: (patientId: number) => request<Record<string, unknown>>(`/api/v1/patients/${patientId}/growth-chart`),
  specialtyTemplates: () => request<Record<string, { key: string; label: string; multiline?: boolean; group?: string; group_label?: string }[]>>('/api/v1/specialty-templates'),
  templateOptions: () => request<{ id: string; label: string }[]>('/api/v1/specialty-template-options'),
  suggestTemplate: (diagnosis: string) =>
    request<{ template: string | null; fields: { key: string; label: string; multiline?: boolean }[] }>(
      `/api/v1/specialty-templates/suggest?diagnosis=${encodeURIComponent(diagnosis)}`,
    ),
  calcEgfr: (data: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/calculators/egfr', { method: 'POST', body: JSON.stringify(data) }),
  calcHomaIr: (data: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/calculators/homa-ir', { method: 'POST', body: JSON.stringify(data) }),
  calcCorrectedCalcium: (data: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/calculators/corrected-calcium', { method: 'POST', body: JSON.stringify(data) }),
  calcSteroid: (data: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/calculators/steroid-conversion', { method: 'POST', body: JSON.stringify(data) }),
  calcPreventAscvd: (data: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/calculators/prevent-ascvd', { method: 'POST', body: JSON.stringify(data) }),
  instructionBilingual: (text: string) =>
    request<{ english: string; kannada: string; bilingual: string | null }>(
      '/api/v1/calculators/instruction-bilingual',
      { method: 'POST', body: JSON.stringify({ text }) },
    ),
  appointments: () => request<Appointment[]>('/api/v1/appointments'),
  appointmentCalendar: (year: number, month: number) =>
    request<{ year: number; month: number; days: { date: string; count: number }[] }>(
      `/api/v1/appointments/calendar?year=${year}&month=${month}`,
    ),
  createAppointment: (data: Record<string, unknown>) => request<Appointment>('/api/v1/appointments', { method: 'POST', body: JSON.stringify(data) }),
  updateAppointmentStatus: (id: number, status: string) =>
    request<{ success: boolean }>(`/api/v1/appointments/${id}/status?status=${encodeURIComponent(status)}`, { method: 'PATCH' }),
  bills: () => request<Bill[]>('/api/v1/bills'),
  createBill: (data: Record<string, unknown>) => request<Bill>('/api/v1/bills', { method: 'POST', body: JSON.stringify(data) }),
  analytics: () => request<AnalyticsData>('/api/v1/analytics'),
};
