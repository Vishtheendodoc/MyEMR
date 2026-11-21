import type { LabResult } from '../api/client';

export function latestLabRows(labs: LabResult[]): LabResult[] {
  const sorted = [...labs].sort((a, b) => {
    const byDate = a.result_date.localeCompare(b.result_date);
    return byDate !== 0 ? byDate : a.id - b.id;
  });
  const byName = new Map<string, LabResult>();
  for (const lab of sorted) {
    const key = lab.test_name.trim().toLowerCase();
    if (key) byName.set(key, lab);
  }
  return [...byName.values()].sort((a, b) => a.test_name.localeCompare(b.test_name));
}
