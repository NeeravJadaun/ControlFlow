const TONE_MAP: Record<string, "neutral" | "success" | "warning" | "danger" | "info"> = {
  open: "info",
  in_progress: "info",
  pending_review: "warning",
  escalated: "danger",
  resolved: "success",
  closed: "neutral",
  draft: "neutral",
  approved: "success",
  rejected: "danger",
  expired: "danger",
  pass: "success",
  fail: "danger",
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
  not_started: "neutral",
  pending_documentation: "warning",
  documented: "success",
  review_due: "warning",
  pending: "neutral",
  sent: "info",
  acknowledged: "success",
  failed: "danger",
};

export function StatusBadge({ value }: { value: string }) {
  const tone = TONE_MAP[value] ?? "neutral";
  return <span className={`badge badge-${tone}`}>{value.replace(/_/g, " ")}</span>;
}
