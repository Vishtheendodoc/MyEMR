const ZONE = 'Asia/Kolkata';

function hasZone(value: string) {
  return /Z$/i.test(value) || /[+-]\d{2}:\d{2}$/.test(value);
}

/** Stored visit, bill, and result clocks are UTC. Date-only values stay on that calendar day. */
export function parseUtcInstant(value: string): Date {
  const raw = value.trim().replace(' ', 'T');
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return new Date(`${raw}T12:00:00Z`);
  return new Date(hasZone(raw) ? raw : `${raw}Z`);
}

function isDateOnly(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value.trim());
}

export function formatClinicDate(value?: string | null): string {
  if (!value) return '—';
  const raw = value.trim();
  if (isDateOnly(raw)) {
    const [year, month, day] = raw.split('-').map(Number);
    return new Date(year, month - 1, day).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }
  const parsed = parseUtcInstant(raw);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', {
    timeZone: ZONE,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function formatClinicDateTime(value?: string | null): string {
  const raw = value && value.trim() ? value.trim() : new Date().toISOString();
  if (isDateOnly(raw)) return formatClinicDate(raw);
  const parsed = parseUtcInstant(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString('en-IN', {
    timeZone: ZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

export function formatClinicClock(value?: string | null): string {
  if (!value) return '—';
  const parsed = parseUtcInstant(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString('en-IN', {
    timeZone: ZONE,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function clinicDayKey(value?: string | null): string {
  if (!value) return '';
  const raw = value.trim();
  if (isDateOnly(raw)) return raw;
  const parsed = parseUtcInstant(raw);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleDateString('en-CA', { timeZone: ZONE });
}

export function clinicTodayKey(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: ZONE });
}
