export type PaymentPart = { method: string; amount: number };

/** Two collected amounts become separate payment rows. One amount stays on the existing field. */
export function collectionBody(
  primaryAmount: number,
  primaryMethod: string,
  secondAmount: number,
  secondMethod: string,
) {
  const parts: PaymentPart[] = [];
  if (primaryAmount > 0) parts.push({ method: primaryMethod, amount: Math.round(primaryAmount * 100) / 100 });
  if (secondAmount > 0) parts.push({ method: secondMethod, amount: Math.round(secondAmount * 100) / 100 });
  if (parts.length < 2) return {};
  return {
    payments: parts,
    payment_method: parts.map(part => part.method).join(' + '),
  };
}
