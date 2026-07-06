import { FG_SITES } from '../components/PcosScoringPanel';

const LUDWIG_DETAILS: Record<string, string> = {
  I: 'thinning on crown; frontal hairline preserved',
  II: 'pronounced rarefaction on crown; frontal hairline preserved',
  III: 'full baldness on crown; frontal hairline preserved',
};

const PCOS_EXAM_LINE_PATTERNS = [
  /^Modified Ferriman-Gallwey:.*$/gm,
  /^FG sites:.*$/gm,
  /^Ludwig grade:.*$/gm,
];

export function stripPcosExaminationLines(examination: string): string {
  let text = examination || '';
  for (const pattern of PCOS_EXAM_LINE_PATTERNS) {
    text = text.replace(pattern, '');
  }
  return text.replace(/\n{3,}/g, '\n\n').trim();
}

export function buildPcosExaminationLines(specialtyData: Record<string, string>): string[] {
  const lines: string[] = [];
  const hasFgScore = FG_SITES.some(s => {
    const v = specialtyData[s.key];
    return v !== undefined && v !== '';
  });

  if (hasFgScore || specialtyData.ferriman_gallwey_total) {
    const total = FG_SITES.reduce((sum, s) => sum + (Number(specialtyData[s.key]) || 0), 0);
    const interp = specialtyData.fg_interpretation;
    lines.push(
      `Modified Ferriman-Gallwey: ${total}/36${interp ? ` — ${interp}` : ''}.`,
    );
    const siteParts = FG_SITES
      .filter(s => specialtyData[s.key] !== undefined && specialtyData[s.key] !== '')
      .map(s => `${s.label} ${specialtyData[s.key]}`)
      .join(', ');
    if (siteParts) {
      lines.push(`FG sites: ${siteParts}.`);
    }
  }

  const ludwig = specialtyData.ludwig_grade?.trim();
  if (ludwig) {
    const detail = LUDWIG_DETAILS[ludwig.toUpperCase()] || LUDWIG_DETAILS[ludwig];
    lines.push(`Ludwig grade: ${ludwig.toUpperCase()}${detail ? ` — ${detail}` : ''}.`);
  }

  return lines;
}

export function mergePcosScoresIntoExamination(
  examination: string,
  specialtyData: Record<string, string>,
): string {
  const scoreLines = buildPcosExaminationLines(specialtyData);
  const base = stripPcosExaminationLines(examination);
  if (!scoreLines.length) return base;
  const block = scoreLines.join('\n');
  return base ? `${base}\n${block}` : block;
}
