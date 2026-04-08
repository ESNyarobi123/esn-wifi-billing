export function formatMoney(amount: string, currency = "TZS") {
  const n = Number.parseFloat(amount);
  if (Number.isNaN(n)) return `${amount} ${currency}`;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currency}`;
  }
}

export function formatDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function shortId(id: string, keep = 8) {
  if (id.length <= keep + 3) return id;
  return `${id.slice(0, keep)}…`;
}
