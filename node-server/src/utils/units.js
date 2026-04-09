function toBigInt(value) {
  if (value === null || value === undefined) return 0n;
  if (typeof value === 'bigint') return value;
  if (typeof value === 'number') return Number.isFinite(value) ? BigInt(Math.trunc(value)) : 0n;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return 0n;
    if (trimmed.startsWith('0x') || trimmed.startsWith('0X')) return BigInt(trimmed);
    if (/^\d+$/.test(trimmed)) return BigInt(trimmed);
    return 0n;
  }
  return 0n;
}

function normalizeDecimals(decimals) {
  if (decimals === null || decimals === undefined) return null;
  const d = typeof decimals === 'string' ? Number.parseInt(decimals, 10) : Number(decimals);
  if (!Number.isFinite(d) || d < 0) return null;
  return Math.trunc(d);
}

export function formatUnits(rawAmount, decimals) {
  const d = normalizeDecimals(decimals);
  if (d === null) return String(rawAmount ?? '0');

  const amount = toBigInt(rawAmount);
  if (d === 0) return amount.toString(10);

  const base = 10n ** BigInt(d);
  const whole = amount / base;
  const fraction = amount % base;

  if (fraction === 0n) return whole.toString(10);

  const fractionStr = fraction.toString(10).padStart(d, '0').replace(/0+$/, '');
  return `${whole.toString(10)}.${fractionStr}`;
}

