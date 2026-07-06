import { CAS_ITEMS, TED_SEVERITY_OPTIONS, WHO_GOITRE_OPTIONS } from '../components/ThyroidScoringPanel';

const THYROID_EXAM_LINE_PATTERNS = [
  /^WHO goitre:.*$/gm,
  /^Clinical Activity Score:.*$/gm,
  /^CAS items:.*$/gm,
  /^Thyroid eye disease severity:.*$/gm,
  /^Proptosis:.*$/gm,
];

export function stripThyroidExaminationLines(examination: string): string {
  let text = examination || '';
  for (const pattern of THYROID_EXAM_LINE_PATTERNS) {
    text = text.replace(pattern, '');
  }
  return text.replace(/\n{3,}/g, '\n\n').trim();
}

export function buildThyroidExaminationLines(specialtyData: Record<string, string>): string[] {
  const lines: string[] = [];

  const who = specialtyData.who_goitre_grade?.trim();
  if (who !== undefined && who !== '') {
    const opt = WHO_GOITRE_OPTIONS.find(o => o.grade === who);
    lines.push(`WHO goitre: Grade ${who}${opt ? ` — ${opt.detail}` : ''}.`);
  }

  const hasCas = CAS_ITEMS.some(item => specialtyData[item.key] === '1');
  const casTotal = specialtyData.cas_total
    ?? String(CAS_ITEMS.reduce((sum, item) => sum + (specialtyData[item.key] === '1' ? 1 : 0), 0));
  if (hasCas || specialtyData.cas_interpretation) {
    const interp = specialtyData.cas_interpretation || '';
    lines.push(`Clinical Activity Score: ${casTotal}/7${interp ? ` — ${interp}` : ''}.`);
    const casParts = CAS_ITEMS
      .filter(item => specialtyData[item.key] === '1')
      .map(item => item.label)
      .join(', ');
    if (casParts) lines.push(`CAS items: ${casParts}.`);
  }

  const ted = specialtyData.ted_severity?.trim();
  if (ted) {
    const opt = TED_SEVERITY_OPTIONS.find(o => o.grade === ted);
    lines.push(`Thyroid eye disease severity: ${opt?.title || ted}${opt ? ` — ${opt.detail}` : ''}.`);
  }

  const proptosis = specialtyData.proptosis?.trim();
  if (proptosis) {
    lines.push(`Proptosis: ${proptosis} mm.`);
  }

  return lines;
}

export function mergeThyroidScoresIntoExamination(
  examination: string,
  specialtyData: Record<string, string>,
): string {
  const scoreLines = buildThyroidExaminationLines(specialtyData);
  const base = stripThyroidExaminationLines(examination);
  if (!scoreLines.length) return base;
  const block = scoreLines.join('\n');
  return base ? `${base}\n${block}` : block;
}
