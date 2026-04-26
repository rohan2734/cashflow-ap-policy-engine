import { cn } from "@/lib/utils"

interface DecisionBannerProps {
  decision: string
  reasons: string[]
  triggeredRuleIds: string[]
}

const STYLES: Record<string, string> = {
  APPROVE: "bg-green-50 border-green-400 text-green-800",
  ESCALATE: "bg-amber-50 border-amber-400 text-amber-800",
  REJECT: "bg-red-50 border-red-400 text-red-800",
}

export function DecisionBanner({ decision, reasons, triggeredRuleIds }: DecisionBannerProps) {
  return (
    <div className={cn("rounded-lg border-2 p-6", STYLES[decision] ?? "bg-muted border-border text-foreground")}>
      <p className="text-2xl font-bold mb-2">{decision}</p>
      {triggeredRuleIds.length > 0 && (
        <p className="text-sm mb-2">Triggered rules: {triggeredRuleIds.join(", ")}</p>
      )}
      <ul className="text-sm list-disc list-inside space-y-1">
        {reasons.map((r, i) => <li key={i}>{r}</li>)}
      </ul>
    </div>
  )
}
