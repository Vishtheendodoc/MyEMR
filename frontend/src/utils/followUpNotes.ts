function dateWords(isoDate: string): string {
  return new Date(`${isoDate.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).replace(/,/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
}

/** Notes that only repeat the scheduled next-visit date are not shown again. */
export function followUpNotesForDisplay(notes: string | null | undefined, followUpDate: string | null | undefined): string {
  const text = (notes || '').trim();
  if (!text) return '';
  const iso = (followUpDate || '').slice(0, 10);
  const target = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? dateWords(iso) : '';
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(line => {
      if (!line) return false;
      const match = line.match(/^review on\s+(.+)$/i);
      if (!match || !target) return true;
      const spoken = match[1].replace(/,/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
      return spoken !== target;
    })
    .join('\n');
}
