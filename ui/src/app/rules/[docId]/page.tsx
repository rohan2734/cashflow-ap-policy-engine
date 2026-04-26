"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { getRules, getReviewThreshold, type RulesListResponse } from "@/lib/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ConfidenceBadge } from "@/components/ConfidenceBadge"

export default function RulesPage() {
  const { docId } = useParams<{ docId: string }>()
  const [data, setData] = useState<RulesListResponse | null>(null)
  const [threshold, setThreshold] = useState(0.5)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getRules(docId), getReviewThreshold()])
      .then(([rules, t]) => { setData(rules); setThreshold(t.threshold) })
      .catch(e => setError(String(e)))
  }, [docId])

  if (error) return <p className="text-red-600">{error}</p>
  if (!data) return <p className="text-muted-foreground">Loading…</p>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Rules — <span className="font-mono text-lg">{docId}</span></h1>
      <p className="text-muted-foreground text-sm">{data.rules.length} rules extracted</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Rule ID</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Source Clauses</TableHead>
            <TableHead>Condition</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rules.map(r => (
            <TableRow key={r.rule_id}>
              <TableCell className="font-mono text-xs">{r.rule_id}</TableCell>
              <TableCell className="font-semibold">{r.action}</TableCell>
              <TableCell><ConfidenceBadge confidence={r.confidence} threshold={threshold} /></TableCell>
              <TableCell className="text-xs">{r.source_clauses.join(", ")}</TableCell>
              <TableCell>
                <pre className="text-xs bg-muted rounded p-1 max-w-xs overflow-auto">
                  {JSON.stringify(r.condition, null, 2)}
                </pre>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
