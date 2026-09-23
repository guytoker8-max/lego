/**
 * Small display helpers shared by the screens.
 */

/**
 * Money, always with both minor digits and thousands separated.
 *
 * The server sends a rounded float, so `477.9` arrives for four hundred and
 * seventy-seven and ninety agorot. Printed raw that reads as a truncation
 * rather than a price, which is a bad look on the one number a customer is
 * deciding on.
 */
export function money(symbol: string, amount: number | string): string {
  const n = typeof amount === 'number' ? amount : Number(amount);
  if (!Number.isFinite(n)) return `${symbol}${amount}`;
  return `${symbol}${n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * A country code as a person would read it.
 *
 * "We ship to IL for now" is a line about a country nobody calls IL. Falls
 * back to the code where the runtime has no display names, which is better
 * than a blank.
 */
export function countryName(code: string): string {
  const c = (code || '').toUpperCase();
  try {
    const names = new (Intl as any).DisplayNames(undefined, { type: 'region' });
    return names.of(c) || c;
  } catch {
    return c;
  }
}
