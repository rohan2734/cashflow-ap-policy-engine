import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfidenceBadge } from "@/components/ConfidenceBadge"
import type { RuleResponse } from "@/lib/api"

interface RuleCardProps {
  rule: RuleResponse
  threshold: number
}

export function RuleCard({ rule, threshold }: RuleCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-mono">{rule.rule_id}</CardTitle>
          <div className="flex gap-2 items-center">
            <span className="text-sm font-semibold">{rule.action}</span>
            <ConfidenceBadge confidence={rule.confidence} threshold={threshold} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-1">
        <p>Clauses: {rule.source_clauses.join(", ")}</p>
        <p className="font-mono text-xs bg-muted rounded p-2 mt-1 overflow-auto">
          {JSON.stringify(rule.condition, null, 2)}
        </p>
      </CardContent>
    </Card>
  )
}
