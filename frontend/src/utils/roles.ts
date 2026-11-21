export type AppRole = 'doctor' | 'registration' | 'billing' | 'pharmacy' | string;

export const ROLE_LABELS: Record<string, string> = {
  doctor: 'Doctor',
  nurse: 'Nurse',
  registration: 'Registration desk',
  billing: 'Billing desk',
  pharmacy: 'Pharmacy',
};

export const ROLE_HOME: Record<string, string> = {
  doctor: '/',
  nurse: '/',
  registration: '/patients',
  billing: '/billing',
  pharmacy: '/pharmacy',
};

/** Paths (prefix match) each role may open. Doctor may open everything. */
const ROLE_PATHS: Record<string, string[]> = {
  doctor: ['*'],
  registration: ['/', '/patients', '/appointments', '/billing', '/reminders', '/messages', '/follow-ups', '/profile'],
  billing: ['/', '/billing', '/finance', '/day-close', '/patients', '/profile'],
  pharmacy: ['/', '/pharmacy', '/stock-desk', '/finance', '/medications', '/patients', '/profile'],
};

/** Clinical chart paths desk staff must not open, even under /patients. */
const DESK_BLOCKED = [
  '/visits/',
  '/visits/',
  '/prescribe',
  '/prescription-preview',
  '/diabetes',
  '/growth',
  '/timeline',
  '/labs',
];

function isDeskBlocked(pathname: string): boolean {
  if (pathname.includes('/visits/')) return true;
  if (pathname.includes('/360')) return true;
  if (pathname.includes('/observations')) return true;
  if (pathname.includes('/intelligence')) return true;
  if (pathname.includes('/medication-safety')) return true;
  if (/\/patients\/\d+\/visits\//.test(pathname)) return true;
  return DESK_BLOCKED.some(part => pathname.includes(part));
}

export function roleHome(role: string) {
  return ROLE_HOME[role] || '/';
}

const NURSE_BLOCKED = ['/billing', '/finance', '/day-close', '/pharmacy', '/stock-desk', '/staff', '/analytics', '/medications', '/diagnoses'];

export function canAccessPath(role: string, pathname: string): boolean {
  if (role === 'doctor' || role === 'admin') return true;
  if (role === 'nurse') return !NURSE_BLOCKED.some(part => pathname === part || pathname.startsWith(`${part}/`));
  if (isDeskBlocked(pathname)) return false;
  const allowed = ROLE_PATHS[role] || ['/profile'];
  if (allowed.includes('*')) return true;
  return allowed.some(p => {
    if (p === '/') return pathname === '/';
    return pathname === p || pathname.startsWith(`${p}/`);
  });
}

export function navVisible(role: string, path: string): boolean {
  return canAccessPath(role, path);
}
