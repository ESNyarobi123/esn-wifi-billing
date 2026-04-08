/** Accessible description — use with Badge aria-label. */
export function paymentStatusAriaLabel(status: string): string {
  return `Payment status: ${status}`;
}

export function paymentStatusVariant(status: string): "success" | "warning" | "destructive" | "secondary" {
  const s = status.toLowerCase();
  if (s.includes("success") || s === "paid") return "success";
  if (s.includes("pending") || s.includes("processing")) return "warning";
  if (s.includes("fail") || s.includes("cancel")) return "destructive";
  return "secondary";
}
