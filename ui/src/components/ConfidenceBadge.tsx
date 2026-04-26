import { Badge } from "@/components/ui/badge"

interface ConfidenceBadgeProps {
  confidence: number
  threshold: number
}

export function ConfidenceBadge({ confidence, threshold }: ConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100)
  if (confidence >= 0.8) {
    return <Badge variant="success">{pct}%</Badge>
  }
  if (confidence >= threshold) {
    return <Badge variant="warning">{pct}%</Badge>
  }
  return <Badge variant="danger">{pct}% — Needs Review</Badge>
}
