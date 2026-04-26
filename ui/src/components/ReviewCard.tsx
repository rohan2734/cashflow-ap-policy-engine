"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ConfidenceBadge } from "@/components/ConfidenceBadge"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { patchRule } from "@/lib/api"
import type { ReviewRuleResponse } from "@/lib/api"

interface ReviewCardProps {
  rule: ReviewRuleResponse
  threshold: number
  onResolved: (ruleId: string) => void
}

export function ReviewCard({ rule, threshold, onResolved }: ReviewCardProps) {
  const [pending, setPending] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  function handleClick(action: string) {
    setPending(action)
    setOpen(true)
  }

  async function confirm() {
    if (!pending) return
    await patchRule(rule.rule_id, pending)
    setOpen(false)
    onResolved(rule.rule_id)
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-mono">{rule.rule_id}</CardTitle>
            <ConfidenceBadge confidence={rule.confidence} threshold={threshold} />
          </div>
          <p className="text-xs text-muted-foreground">Doc: {rule.doc_id} · Action: {rule.action}</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">Clauses: {rule.source_clauses.join(", ")}</p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" className="text-green-700 border-green-300 hover:bg-green-50" onClick={() => handleClick("APPROVE")}>Approve</Button>
            <Button size="sm" variant="outline" className="text-amber-700 border-amber-300 hover:bg-amber-50" onClick={() => handleClick("ESCALATE")}>Escalate</Button>
            <Button size="sm" variant="outline" className="text-red-700 border-red-300 hover:bg-red-50" onClick={() => handleClick("REJECT")}>Reject</Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Override</DialogTitle>
            <DialogDescription>
              Set action for {rule.rule_id} to <strong>{pending}</strong>?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={confirm}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
