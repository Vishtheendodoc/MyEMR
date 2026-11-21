const PREFIX = 'endo-emr-visit-draft:';

export type VisitDraftPayload = {
  form: Record<string, string>;
  specialtyData: Record<string, string>;
  preventForm?: Record<string, unknown>;
  preventResult?: Record<string, unknown> | null;
  savedAt: string;
};

export function draftKey(patientId: number | string, visitId?: number | string | null) {
  return visitId ? `${PREFIX}visit:${visitId}` : `${PREFIX}patient:${patientId}`;
}

export function saveVisitDraft(key: string, payload: Omit<VisitDraftPayload, 'savedAt'>) {
  try {
    localStorage.setItem(key, JSON.stringify({ ...payload, savedAt: new Date().toISOString() }));
  } catch {
    /* quota / private mode */
  }
}

export function loadVisitDraft(key: string): VisitDraftPayload | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as VisitDraftPayload;
  } catch {
    return null;
  }
}

export function clearVisitDraft(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}
