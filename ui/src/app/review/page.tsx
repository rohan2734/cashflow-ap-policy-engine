"use client"

import { useEffect, useState } from "react"
import { getReviewQueue, getReviewThreshold, type ReviewRuleResponse } from "@/lib/api"
import { ReviewCard } from "@/components/ReviewCard"

export default function ReviewPage() {
  const [rules, setRules] = useState<ReviewRuleResponse[]>([])
  const [threshold, setThreshold] = useState(0.5)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getReviewQueue(), getReviewThreshold()])
      .then(([q, t]) => { setRules(q.rules); setThreshold(t.threshold) })
      .catch(e => setError(String(e)))
  }, [])

  function handleResolved(ruleId: string) {
    setRules(prev => prev.filter(r => r.rule_id !== ruleId))
  }

  if (error) return <p className="text-red-600">{error}</p>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Review Queue</h1>
      {rules.length === 0 ? (
        <p className="text-muted-foreground">No rules pending review.</p>
      ) : (
        <div className="space-y-4">
          {rules.map(r => (
            <ReviewCard key={r.rule_id} rule={r} threshold={threshold} onResolved={handleResolved} />
          ))}
        </div>
      )}
    </div>
  )
}
