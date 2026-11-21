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
  clinic_id?: number;
  acting_doctor_id?: number | null;
  acting_clinic_id?: number | null;
  is_active?: boolean;
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
  allergies?: string | null;
  problem_list?: string | null;
  date_registered: string;
  doctor_id: number | null;
  registration_status?: string | null;
}

export interface PatientDuplicateHit {
  id: number;
  name: string;
  mrd_number?: string | null;
  contact?: string | null;
  match?: string;
}

export interface DayCloseSummary {
  date?: string;
  cash?: number;
  upi?: number;
  card?: number;
  other?: number;
  billed?: number;
  collected?: number;
  bank?: number;
  locked?: boolean;
  locked_at?: string | null;
  notes?: string | null;
  opening_cash?: number;
  closing_cash?: number;
}

export interface QueueVitals {
  height?: number | null;
  weight?: number | null;
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  pulse?: number | null;
  temperature?: number | null;
  spo2?: number | null;
}

export interface VisitSummary {
  id: number;
  visit_date: string;
  visit_type: string;
  status?: string | null;
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
  prescribed_quantity?: number | null;
  dispensed_quantity?: number | null;
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
  ordered_investigations?: string | null;
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
  price?: number | null;
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
  today?: {
    date: string;
    consultations: TodayConsult[];
    booked: number;
    waiting: number;
    in_consult: number;
    done: number;
    new: number;
    revisit: number;
    walk_in: number;
    online: number;
  };
}

export interface TodayConsult {
  appointment_id?: number | null;
  visit_id?: number | null;
  patient_id: number;
  patient_name: string;
  patient_mrd?: string | null;
  patient_age?: string | null;
  patient_sex?: string | null;
  scheduled_at?: string | null;
  token_number?: number | null;
  status: string;
  channel: string;
  kind: string;
  complaint?: string | null;
}

export interface ClinicalObservation {
  id: number;
  patient_id: number;
  visit_id: number | null;
  observation_code: string;
  observation_name: string;
  value_numeric: number | null;
  value_text: string;
  unit: string | null;
  reference_range_low: number | null;
  reference_range_high: number | null;
  reference_range: string | null;
  observed_at: string;
  source: string;
  source_record_type: string | null;
  source_record_id: number | null;
  verification_status: string;
  verified_by: number | null;
  created_at: string;
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

export interface Patient360Snapshot {
  generated_at: string;
  display_timezone: string;
  disclaimer: string;
  overview: {
    id: number;
    name: string;
    mrd_number: string | null;
    age: string;
    sex: string;
    contact: string | null;
    address: string | null;
    date_of_birth: string | null;
    date_registered: string;
    allergies: string | null;
    problem_list: string | null;
    comorbidities: string | null;
    visit_count: number;
    active_diagnoses: { text: string; visit_id: number; visit_date: string }[];
    current_medications: {
      visit_id: number;
      visit_date: string;
      drug_name: string;
      generic_name: string | null;
      dosage: string | null;
      frequency: string | null;
      timing: string | null;
      duration: string | null;
      dose_morning: string | null;
      dose_afternoon: string | null;
      dose_evening: string | null;
    }[];
    current_medications_visit_id: number | null;
    current_medications_visit_date: string | null;
    prompts: { code: string; severity: string; title: string; explanation: string; triggering: string[] }[];
  };
  parameters: {
    code: string;
    name: string;
    group: string;
    unit: string | null;
    reference_range: string | null;
    note: string | null;
    latest: { date: string; value_text: string; value_numeric: number | null; unit: string | null; source: string } | null;
    previous: { date: string; value_text: string; value_numeric: number | null; unit: string | null; source: string } | null;
  }[];
  trends: {
    id: string;
    title: string;
    series: { code: string; name: string; unit: string | null; points: { date: string; value: number }[] }[];
  }[];
  cgm: { time: string; glucose: number }[];
  timeline: { at: string; kind: string; title: string; detail: string | null; ref_type: string | null; ref_id: number | null }[];
  comparison: {
    available: boolean;
    disclaimer: string;
    previous_visit_id: number | null;
    current_visit_id: number | null;
    previous_visit_date: string | null;
    current_visit_date: string | null;
    previous_visit_status: string | null;
    current_visit_status: string | null;
    medication_note: string | null;
    medication_changes: { change: string; drug_name: string; generic_name: string | null; previous: string | null; current: string | null }[];
    parameter_changes: { code: string; name: string; unit: string | null; previous_value: string | null; current_value: string | null; previous_date: string | null; current_date: string | null; direction: string }[];
    vital_changes: { code: string; name: string; unit: string | null; previous_value: string | null; current_value: string | null; previous_date: string | null; current_date: string | null; direction: string }[];
    diagnosis_previous: string | null;
    diagnosis_current: string | null;
    diagnoses_added: string[];
    diagnoses_removed: string[];
    investigations_previous: string | null;
    investigations_current: string | null;
  };
}

export interface FollowUpItem {
  visit_id: number;
  patient_id: number;
  patient_name: string;
  patient_mrd: string | null;
  patient_contact?: string | null;
  follow_up_date: string;
  follow_up_notes?: string | null;
  diagnosis: string | null;
  days_overdue: number;
  days_until?: number;
  bucket?: 'overdue' | 'today' | 'upcoming' | 'cancelled' | 'done' | string;
}

export interface ReminderQueueItem {
  id: string;
  source_type: 'appointment' | 'follow_up' | string;
  source_id: number;
  visit_id?: number | null;
  patient_id: number;
  patient_name: string;
  patient_mrd: string | null;
  patient_contact: string | null;
  due_at: string;
  remind_on?: string;
  auto_due_today?: boolean;
  label: string;
  detail: string | null;
  message: string;
  whatsapp_url: string | null;
  already_reminded: boolean;
  last_reminded_at: string | null;
}

export interface ReminderSendResult {
  id: number;
  status: string;
  channel: string;
  whatsapp_url: string | null;
  phone: string | null;
  message: string;
  error: string | null;
  auto_send_available: boolean;
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
  patient_contact?: string | null;
  patient_mrd?: string | null;
  registration_status?: string | null;
  scheduled_at: string;
  duration_minutes: number;
  status: string;
  notes: string | null;
  token_number?: number | null;
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  pulse?: number | null;
  weight?: number | null;
}

export interface ClinicProfile {
  clinic_id: number;
  name: string;
  address?: string | null;
  phone?: string | null;
  gstin?: string | null;
  signatory?: string | null;
  signature_data?: string | null;
}

export interface PriceItem {
  id: number;
  kind: string;
  name: string;
  code?: string | null;
  rate: number;
  gst_percent: number;
  detail?: string | null;
  active?: boolean;
}

export interface BillLine {
  description: string;
  procedure_code?: string | null;
  quantity?: number;
  rate?: number;
  base_amount?: number;
  gst_percent?: number;
  gst_amount?: number;
  note?: string | null;
}

export interface Bill {
  id: number;
  visit_id: number;
  patient_id: number;
  patient_name: string | null;
  patient_mrd?: string | null;
  patient_age?: string | null;
  patient_sex?: string | null;
  description: string;
  amount: number;
  base_amount?: number | null;
  gst_percent?: number;
  gst_amount?: number;
  discount_amount?: number;
  amount_paid?: number;
  line_items?: BillLine[] | null;
  procedure_code: string | null;
  payment_status: string;
  payment_method: string | null;
  invoice_number?: string | null;
  category?: string | null;
  bill_type?: string | null;
  created_at?: string;
  refund_amount?: number | null;
  refund_reason?: string | null;
  patient_contact?: string | null;
  round_off?: number;
  cgst_amount?: number;
  sgst_amount?: number;
  igst_amount?: number;
  credit_note_number?: string | null;
  receipts?: Array<{ amount: number; method: string; kind?: string; note?: string | null; created_at?: string | null }>;
}

export interface BillingVisitOption {
  visit_id: number;
  patient_id: number;
  patient_name: string;
  patient_mrd: string;
  visit_date: string;
  visit_type: string;
  diagnosis: string | null;
  investigation?: string | null;
}

export interface ClinicalAlert {
  id: number;
  rule_code: string;
  rule_version: string;
  title: string;
  explanation: string;
  triggering_parameters: string | null;
  previous_values: string | null;
  recommended_review: string;
  guideline_reference: string;
  severity: string;
  status: string;
  override_reason: string | null;
  created_at: string | null;
}

export interface AnalyticsData {
  diagnosis_distribution: { diagnosis: string; count: number }[];
  visit_volume_by_month: { month: number; count: number }[];
  top_medications: { drug: string; count: number }[];
  revenue_summary: { total_billed: number; total_paid: number; pending: number };
  practice?: {
    clinical: Record<string, number | string | null>;
    business: {
      consultation_revenue: number;
      pharmacy_turnover: number;
      laboratory_revenue: number;
      pharmacy_gross_margin: number | null;
      pharmacy_margin_note: string;
      revenue_note: string;
      consultations_today: number;
      consultations_this_month: number;
      new_patients_this_month: number;
      returning_patients_this_month: number;
      medication_sales: { description: string; amount: number; count: number }[];
      stock_expiring_within_90_days: { item_name: string; expiry_date: string; quantity: number }[];
      dead_stock: { item_name: string; quantity: number }[];
      dead_stock_note: string | null;
      follow_up_conversion_percent: number | null;
      retention_percent: number | null;
    };
  };
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

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
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

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const { access, refresh } = getTokens();
  const headers: Record<string, string> = {
  ...(options.headers as Record<string, string> || {}),
  };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  if (access) headers['Authorization'] = `Bearer ${access}`;

  let res = await fetchWithTimeout(`${API_BASE}${path}`, { ...options, headers }, timeoutMs);

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
      res = await fetchWithTimeout(`${API_BASE}${path}`, { ...options, headers }, timeoutMs);
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
  doctors: () => request<User[]>('/api/v1/auth/doctors'),
  setActingDoctor: (doctorId: number) =>
    request<User>('/api/v1/auth/acting-doctor', { method: 'PATCH', body: JSON.stringify({ doctor_id: doctorId }) }),
  updateProfile: (data: { display_name: string; qualifications?: string; kmc_number?: string }) =>
    request<User>('/api/v1/auth/profile', { method: 'PATCH', body: JSON.stringify(data) }),
  clinicProfile: () => request<ClinicProfile>('/api/v1/clinic/profile'),
  saveClinicProfile: (data: Partial<ClinicProfile>) =>
    request<ClinicProfile>('/api/v1/clinic/profile', { method: 'PUT', body: JSON.stringify(data) }),
  prices: () => request<PriceItem[]>('/api/v1/clinic/prices'),
  savePrice: (data: Partial<PriceItem>) =>
    request<PriceItem>('/api/v1/clinic/prices', { method: 'POST', body: JSON.stringify(data) }),
  updatePrice: (id: number, data: Partial<PriceItem>) =>
    request<PriceItem>(`/api/v1/clinic/prices/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deletePrice: (id: number) => request<void>(`/api/v1/clinic/prices/${id}`, { method: 'DELETE' }),
  stock: () => request<{
    item_name: string;
    quantity: number;
    reorder_level: number;
    low: boolean;
    messy?: boolean;
    batches: { id: number; batch_no: string | null; expiry_date: string | null; quantity: number; expired: boolean; synthetic?: boolean }[];
  }[]>('/api/v1/clinic/stock'),
  addStock: (data: { item_name: string; batch_no?: string; expiry_date?: string; quantity: number; reorder_level?: number }) =>
    request<{ id: number }>('/api/v1/clinic/stock', { method: 'POST', body: JSON.stringify(data) }),
  returnStock: (itemName: string, data: { quantity: number; batch_id?: number; batch_no?: string; expiry_date?: string }) =>
    request<{ id: number }>(`/api/v1/clinic/stock/return/${encodeURIComponent(itemName)}`, { method: 'POST', body: JSON.stringify(data) }),
  writeOffStock: (itemName: string, data: { quantity: number; batch_id?: number }) =>
    request<{ success: boolean }>(`/api/v1/clinic/stock/writeoff/${encodeURIComponent(itemName)}`, { method: 'POST', body: JSON.stringify(data) }),
  consolidateStock: (itemName?: string) =>
    request<{ success: boolean; items_cleaned: number }>(
      `/api/v1/clinic/stock/consolidate${itemName ? `?item_name=${encodeURIComponent(itemName)}` : ''}`,
      { method: 'POST' },
    ),
  staffAccounts: () => request<User[]>('/api/v1/auth/staff'),
  createStaff: (data: { email: string; password: string; display_name: string; role: string }) =>
    request<User>('/api/v1/auth/staff', { method: 'POST', body: JSON.stringify(data) }),
  resetStaffPassword: (id: number, password: string) =>
    request<User>(`/api/v1/auth/staff/${id}`, { method: 'PATCH', body: JSON.stringify({ password }) }),
  setStaffActive: (id: number, is_active: boolean) =>
    request<User>(`/api/v1/auth/staff/${id}`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  checkPatientDuplicates: (params: { name?: string; contact?: string }) => {
    const q = new URLSearchParams();
    if (params.name?.trim()) q.set('name', params.name.trim());
    if (params.contact?.trim()) q.set('contact', params.contact.trim());
    return request<PatientDuplicateHit[]>(`/api/v1/patients/duplicates?${q}`);
  },
  queueVitals: (patientId: number) =>
    request<QueueVitals>(`/api/v1/patients/${patientId}/queue-vitals`),
  appointmentVitals: (patientId: number) =>
    request<QueueVitals>(`/api/v1/patients/${patientId}/queue-vitals`),
  dayCloseSummary: (day?: string) =>
    request<DayCloseSummary>(day ? `/api/v1/day-close?day=${encodeURIComponent(day)}` : '/api/v1/day-close'),
  lockDayClose: (data?: { notes?: string; opening_cash?: number; closing_cash?: number; day?: string }) =>
    request<DayCloseSummary>('/api/v1/day-close', { method: 'POST', body: JSON.stringify(data || {}) }),
  reopenDayClose: (data?: { day?: string }) =>
    request<DayCloseSummary>('/api/v1/day-close/reopen', { method: 'POST', body: JSON.stringify(data || {}) }),
  dayCloseLocks: () => request<Array<{ date: string; locked_at?: string | null; notes?: string | null }>>('/api/v1/day-close/locks'),
  whatsappInvoice: (billId: number) =>
    request<{ whatsapp_url?: string | null; message?: string; phone?: string | null }>(
      `/api/v1/bills/${billId}/whatsapp`,
      { method: 'POST' },
    ),
  uploadEducationVideo: (file: File, title: string) => {
    const body = new FormData();
    body.append('file', file);
    body.append('title', title);
    return request<{ token: string; title: string; bytes: number; url: string }>(
      '/api/v1/messages/videos',
      { method: 'POST', body },
      120000,
    );
  },
  messageContacts: () => request<Array<{ id: number; name: string; phone: string; list_kind?: string }>>('/api/v1/messages/contacts'),
  saveMessageContact: (data: { name: string; phone: string; list_kind?: string }) =>
    request<{ id: number; name: string; phone: string; list_kind?: string }>('/api/v1/messages/contacts', { method: 'POST', body: JSON.stringify(data) }),
  deleteMessageContact: (id: number) =>
    request<{ success: boolean }>(`/api/v1/messages/contacts/${id}`, { method: 'DELETE' }),
  sendWhatsAppText: (data: { phone: string; name: string; kind: string; message?: string; video_title?: string; video_url?: string }) =>
    request<{ status: string; phone: string }>('/api/v1/messages/send-text', { method: 'POST', body: JSON.stringify(data) }, 60000),
  sendWhatsAppVideo: (data: { phone: string; name: string; token: string; message?: string; video_title?: string }) =>
    request<{ status: string; phone: string }>('/api/v1/messages/send-video', { method: 'POST', body: JSON.stringify(data) }, 60000),
  broadcastMessage: (data: { kind: string; message?: string; video_title?: string; video_url?: string; deliver?: boolean; as_file?: boolean; audience?: string }) =>
    request<{
      audience: number;
      skipped_without_phone: number;
      delivered: number;
      failed: number;
      twilio: boolean;
      items: Array<{ patient_id: number | null; name: string; phone: string; whatsapp_url: string | null; status: string }>;
    }>('/api/v1/messages/broadcast', { method: 'POST', body: JSON.stringify(data) }),
  whatsappPrescription: (visitId: number) =>
    request<{ whatsapp_url?: string | null; message?: string; phone?: string | null }>(
      `/api/v1/visits/${visitId}/prescription/whatsapp`,
      { method: 'POST' },
    ),
  dashboard: () => request<DashboardData>('/api/v1/dashboard'),
  patients: (q?: string, search_type?: string) =>
    request<Patient[]>(`/api/v1/patients?${new URLSearchParams({ ...(q ? { q } : {}), ...(search_type ? { search_type } : {}) })}`),
  patient: (id: number) => request<PatientDetail>(`/api/v1/patients/${id}`),
  patient360: (id: number) => request<Patient360Snapshot>(`/api/v1/patients/${id}/patient-360`),
  createPatient: (data: Omit<Patient, 'id' | 'date_registered' | 'doctor_id' | 'registration_status'> & { temporary?: boolean; doctor_id?: number }) =>
    request<Patient>('/api/v1/patients', { method: 'POST', body: JSON.stringify(data) }),
  updatePatient: (id: number, data: Partial<Patient>) =>
    request<Patient>(`/api/v1/patients/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  assignMrd: (id: number) =>
    request<Patient>(`/api/v1/patients/${id}/assign-mrd`, { method: 'POST' }),
  cancelRegistration: (id: number) =>
    request<Patient>(`/api/v1/patients/${id}/cancel`, { method: 'POST' }),
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
  fieldSuggestions: (field: string, q = '') =>
    request<{ value: string; source: string }[]>(
      `/api/v1/suggestions?field=${encodeURIComponent(field)}&q=${encodeURIComponent(q)}`,
    ),
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
  observations: (patientId: number) => request<ClinicalObservation[]>(`/api/v1/patients/${patientId}/observations`),
  createObservation: (patientId: number, data: Record<string, unknown>) =>
    request<ClinicalObservation>(`/api/v1/patients/${patientId}/observations`, { method: 'POST', body: JSON.stringify(data) }),
  verifyObservation: (id: number) =>
    request<ClinicalObservation>(`/api/v1/observations/${id}/verify`, { method: 'POST' }),
  labs: (patientId: number) => request<LabResult[]>(`/api/v1/patients/${patientId}/labs`),
  addLab: (patientId: number, data: Record<string, unknown>) =>
    request<LabResult>(`/api/v1/patients/${patientId}/labs`, { method: 'POST', body: JSON.stringify(data) }),
  deleteLab: (labId: number) => request<void>(`/api/v1/labs/${labId}`, { method: 'DELETE' }),
  imaging: (patientId: number) => request<ImagingResult[]>(`/api/v1/patients/${patientId}/imaging`),
  addImaging: (patientId: number, data: Record<string, unknown>) =>
    request<ImagingResult>(`/api/v1/patients/${patientId}/imaging`, { method: 'POST', body: JSON.stringify(data) }),
  timeline: (patientId: number) => request<TimelineData>(`/api/v1/patients/${patientId}/timeline`),
  followUps: (scope: 'all' | 'overdue' | 'today' | 'upcoming' = 'all', days = 30) =>
    request<FollowUpItem[]>(`/api/v1/follow-ups?scope=${scope}&days=${days}`),
  rescheduleFollowUp: (visitId: number, followUpDate: string, followUpNotes?: string | null, followUpTime?: string) => {
    const params = new URLSearchParams({ follow_up_date: followUpDate });
    if (followUpNotes != null) params.set('follow_up_notes', followUpNotes);
    if (followUpTime) params.set('follow_up_time', followUpTime);
    return request<{ success: boolean; visit_id: number; follow_up_date: string; follow_up_notes: string | null; appointment_id?: number | null; scheduled_at?: string | null }>(
      `/api/v1/visits/${visitId}/follow-up?${params}`,
      { method: 'PATCH' },
    );
  },
  lastPrescriptions: (patientId: number, excludeVisitId?: number) =>
    request<{ source_visit_id: number | null; visit_date: string | null; prescriptions: Prescription[] }>(
      `/api/v1/patients/${patientId}/last-prescriptions${excludeVisitId ? `?exclude_visit_id=${excludeVisitId}` : ''}`,
    ),
  repeatPrescriptions: (visitId: number, sourceVisitId: number) =>
    request<{ success: boolean; copied: number; prescription_ids: number[]; warnings: unknown[] }>(
      `/api/v1/visits/${visitId}/prescriptions/repeat/${sourceVisitId}`,
      { method: 'POST' },
    ),
  remindersStatus: () =>
    request<{ auto_send_available: boolean; channel_default: string; clinic_name: string; doctor_name?: string; rule?: string }>('/api/v1/reminders/status'),
  saveReminderNames: (data: { clinic_name: string; doctor_name: string }) =>
    request<{ clinic_name: string; doctor_name: string }>('/api/v1/reminders/names', { method: 'PATCH', body: JSON.stringify(data) }),
  cancelReminder: (data: { source_type: string; source_id: number }) =>
    request<{ success: boolean }>('/api/v1/reminders/cancel', { method: 'POST', body: JSON.stringify(data) }),
  remindersQueue: (days = 3) => request<ReminderQueueItem[]>(`/api/v1/reminders/queue?days=${days}`),
  sendReminder: (data: { source_type: string; source_id: number; auto_send?: boolean; message?: string }) =>
    request<ReminderSendResult>('/api/v1/reminders/send', { method: 'POST', body: JSON.stringify(data) }),
  remindersAutoRun: () =>
    request<{
      date: string;
      auto_send_available: boolean;
      sent: number;
      queued: number;
      failed: number;
      skipped: number;
      details: { appointment_id: number; patient_name: string; status: string; whatsapp_url?: string | null }[];
    }>('/api/v1/reminders/auto-run', { method: 'POST' }),
  reminderHistory: (limit = 50) =>
    request<{
      id: number;
      patient_id: number;
      patient_name: string | null;
      source_type: string;
      source_id: number;
      channel: string;
      status: string;
      phone: string | null;
      message: string | null;
      error: string | null;
      sent_at: string | null;
      created_at: string | null;
    }[]>(`/api/v1/reminders/history?limit=${limit}`),
  visitCds: (visitId: number) => request<CdsRecommendation[]>(`/api/v1/visits/${visitId}/cds`),
  diabetesDashboard: (patientId: number) => request<{
    hba1c_trend: { date: string; value: string; unit: string | null }[];
    recent_labs?: { test_name: string; value: string; unit: string | null; result_date: string }[];
    cgm_readings: { time: string; glucose: number }[];
    insulin_dosing: { visit_date: string; drug: string; morning: string | null; afternoon: string | null; evening: string | null }[];
    cgm_period_days?: number;
    cgm_metrics?: {
      reading_count: number;
      time_in_range: number | null;
      time_above_range: number | null;
      time_below_range: number | null;
      gmi: number | null;
      coefficient_of_variation: number | null;
      average_glucose: number | null;
      glucose_sd: number | null;
    };
    nocturnal_hypoglycemia?: { count: number; window_local: string };
    postprandial?: { note: string; windows: Record<string, { average: number | null; count: number }> };
    insulin?: { latest_total_daily_units: number | null; units_per_kg: number | null; titration_change_units: number | null };
    diabetes_medicines?: { sglt2_inhibitor: string[]; glp1_receptor_agonist: string[] };
    screening?: { item: string; last_on: string | null; overdue: boolean }[];
    agp?: { hour: number; p50: number | null; count: number }[];
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
  appointments: (day?: string) =>
    request<Appointment[]>(`/api/v1/appointments${day ? `?day=${day}` : ''}`),
  patientAppointments: (patientId: number) =>
    request<Appointment[]>(`/api/v1/patients/${patientId}/appointments`),
  appointmentCalendar: (year: number, month: number) =>
    request<{ year: number; month: number; days: { date: string; count: number }[] }>(
      `/api/v1/appointments/calendar?year=${year}&month=${month}`,
    ),
  createAppointment: (data: Record<string, unknown>) => request<Appointment>('/api/v1/appointments', { method: 'POST', body: JSON.stringify(data) }),
  checkInQueue: (data: { patient_id: number; channel: string; kind: string; doctor_id?: number }) =>
    request<{ appointment_id: number; visit_id: number; token_number: number | null; status: string; channel: string; kind: string }>(
      '/api/v1/queue/check-in',
      { method: 'POST', body: JSON.stringify(data) },
    ),
  updateAppointment: (id: number, data: Record<string, unknown>) =>
    request<Appointment>(`/api/v1/appointments/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  updateAppointmentStatus: (id: number, status: string) =>
    request<{ success: boolean }>(`/api/v1/appointments/${id}/status?status=${encodeURIComponent(status)}`, { method: 'PATCH' }),
  bills: () => request<Bill[]>('/api/v1/bills'),
  bill: (id: number) => request<Bill>(`/api/v1/bills/${id}`),
  billingVisitOptions: () => request<BillingVisitOption[]>('/api/v1/billing/visit-options'),
  billingOrders: () => request<{
    visit_id: number;
    patient_id: number;
    patient_name: string;
    patient_mrd: string | null;
    visit_date: string;
    diagnosis: string | null;
    investigation: string | null;
    billed: boolean;
  }[]>('/api/v1/billing/orders'),
  pharmacyPrescriptions: () => request<{
    visit_id: number;
    patient_id: number;
    patient_name: string;
    patient_mrd: string | null;
    visit_date: string;
    diagnosis: string | null;
    billed: boolean;
    declined?: boolean;
    dispense_note?: string | null;
    prescriptions: Prescription[];
  }[]>('/api/v1/pharmacy/prescriptions'),
  declineDispense: (visitId: number, note: string) =>
    request<{ success: boolean; visit_id: number; declined: number; note: string }>(
      '/api/v1/pharmacy/prescriptions/decline',
      { method: 'POST', body: JSON.stringify({ visit_id: visitId, note }) },
    ),
  createBill: (data: Record<string, unknown>) => request<Bill>('/api/v1/bills', { method: 'POST', body: JSON.stringify(data) }),
  updateBill: (id: number, data: Record<string, unknown>) => request<Bill>(`/api/v1/bills/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  analytics: () => request<AnalyticsData>('/api/v1/analytics'),
  logout: (refreshToken: string) =>
    fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  intelligence: (patientId: number) => request<{ alerts: ClinicalAlert[] }>(`/api/v1/patients/${patientId}/intelligence`),
  acknowledgeAlert: (id: number) => request<ClinicalAlert>(`/api/v1/alerts/${id}/acknowledge`, { method: 'POST' }),
  dismissAlert: (id: number, reason: string) =>
    request<ClinicalAlert>(`/api/v1/alerts/${id}/dismiss`, { method: 'POST', body: JSON.stringify({ reason }) }),
  medicationSafety: (patientId: number) => request<Record<string, unknown>>(`/api/v1/patients/${patientId}/medication-safety`),
  requestSubstitution: (patientId: number, data: Record<string, unknown>) =>
    request<{ id: number; brand_medication_id: number }>(`/api/v1/patients/${patientId}/substitutions`, { method: 'POST', body: JSON.stringify(data) }),
  approveSubstitution: (id: number) =>
    request<{ unchanged: boolean }>(`/api/v1/substitutions/${id}/approve`, { method: 'POST' }),
  interopStatus: () => request<Record<string, { configured?: boolean; certified?: boolean; note?: string }>>('/api/v1/interop/status'),
  finance: (preset: string, dateFrom = '', dateTo = '') => {
    const query = new URLSearchParams({ preset });
    if (dateFrom && dateTo) {
      query.set('date_from', dateFrom);
      query.set('date_to', dateTo);
    }
    return request<Record<string, any>>(`/api/v1/commerce/finance?${query.toString()}`);
  },
  patientBills: (patientId: number) => request<Record<string, any>[]>(`/api/v1/commerce/patients/${patientId}/bills`),
  suppliers: () => request<Record<string, any>[]>('/api/v1/commerce/suppliers'),
  saveSupplier: (data: Record<string, unknown>) => request<Record<string, any>>('/api/v1/commerce/suppliers', { method: 'POST', body: JSON.stringify(data) }),
  medicines: (q: string) => request<Record<string, any>[]>(`/api/v1/commerce/medicines?q=${encodeURIComponent(q)}`),
  saveMedicine: (data: Record<string, unknown>) => request<Record<string, any>>('/api/v1/commerce/medicines', { method: 'POST', body: JSON.stringify(data) }),
  purchases: () => request<Record<string, any>[]>('/api/v1/commerce/purchases'),
  savePurchase: (data: Record<string, unknown>) => request<Record<string, any>>('/api/v1/commerce/purchases', { method: 'POST', body: JSON.stringify(data) }),
  salesReturn: (data: Record<string, unknown>) => request<Record<string, any>>('/api/v1/commerce/sales-returns', { method: 'POST', body: JSON.stringify(data) }),
  salesReturns: () => request<Record<string, any>[]>('/api/v1/commerce/sales-returns'),
  purchaseReturn: (data: Record<string, unknown>) => request<Record<string, any>>('/api/v1/commerce/purchase-returns', { method: 'POST', body: JSON.stringify(data) }),
  expiryReport: () => request<Record<string, any[]>>('/api/v1/commerce/expiry'),
  stockAlerts: () => request<Record<string, any[]>>('/api/v1/commerce/stock-alerts'),
  stockAvailability: (names: string[]) => {
    const params = new URLSearchParams();
    names.forEach(name => params.append('name', name));
    return request<Array<{
      name: string;
      saleable: number;
      batches: Array<{ batch_no?: string | null; expiry_date?: string | null; quantity: number; stock_status?: string }>;
    }>>(`/api/v1/commerce/availability?${params.toString()}`);
  },
  walkInSale: (data: Record<string, unknown>) => request<Bill>('/api/v1/commerce/walk-in', { method: 'POST', body: JSON.stringify(data) }),
  downloadStockAlerts: async () => {
    const { access } = getTokens();
    const res = await fetch(`${API_BASE}/api/v1/commerce/stock-alerts/export`, { headers: access ? { Authorization: `Bearer ${access}` } : {} });
    if (!res.ok) throw new Error('Could not download the stock workbook');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'stock-alerts.xlsx';
    link.click();
    URL.revokeObjectURL(url);
  },
};
