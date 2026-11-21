const KEY = 'endoemr-typed-memory-v1';
const MAX_PER_FIELD = 40;

type Store = Record<string, string[]>;

function readStore(): Store {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}') as Store;
  } catch {
    return {};
  }
}

function writeStore(store: Store) {
  try {
    localStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    /* ignore quota */
  }
}

/** Remember a finished phrase for a field (diagnosis, drug, etc.). */
export function rememberTyped(field: string, value: string | null | undefined) {
  const text = (value || '').trim();
  if (!field || text.length < 2) return;
  // For multi-line fields, remember each meaningful line too
  const parts = text.includes('\n')
    ? [text, ...text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length >= 2)]
    : [text];
  const store = readStore();
  const current = store[field] || [];
  let next = current.filter(item => item.toLowerCase() !== text.toLowerCase());
  for (const part of parts.reverse()) {
    next = [part, ...next.filter(item => item.toLowerCase() !== part.toLowerCase())];
  }
  store[field] = next.slice(0, MAX_PER_FIELD);
  writeStore(store);
}

export function recallTyped(field: string, q = '', limit = 12): string[] {
  const needle = q.trim().toLowerCase();
  const rows = readStore()[field] || [];
  const filtered = needle
    ? rows.filter(item => item.toLowerCase().includes(needle))
    : rows;
  return filtered
    .slice()
    .sort((a, b) => {
      const as = a.toLowerCase().startsWith(needle) ? 0 : 1;
      const bs = b.toLowerCase().startsWith(needle) ? 0 : 1;
      return as - bs || a.length - b.length;
    })
    .slice(0, limit);
}
