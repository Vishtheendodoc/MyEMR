import type { Patient } from '../api/client';

export function chartTarget(pathname: string): { patientId?: number; visitId?: number } {
  const patient = pathname.match(/^\/patients\/(\d+)(?:\/|$)/);
  if (patient) return { patientId: Number(patient[1]) };
  const visit = pathname.match(/^\/visits\/(\d+)(?:\/|$)/);
  if (visit) return { visitId: Number(visit[1]) };
  return {};
}

export function mergePatients(groups: Patient[][]): Patient[] {
  const byId = new Map<number, Patient>();
  groups.forEach(rows => {
    rows.forEach(row => {
      if (!byId.has(row.id)) byId.set(row.id, row);
    });
  });
  return [...byId.values()];
}
