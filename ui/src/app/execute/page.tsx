"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { DecisionBanner } from "@/components/DecisionBanner"
import { executeRules, type ExecuteResponse } from "@/lib/api"

const PLACEHOLDER = JSON.stringify({ invoice_id: "INV-001", amount: 5000, vendor: "ACME" }, null, 2)

export default function ExecutePage() {
  const [docId, setDocId] = useState("")
  const [invoiceJson, setInvoiceJson] = useState(PLACEHOLDER)
  const [result, setResult] = useState<ExecuteResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function run() {
    setError(null)
    let invoice: Record<string, unknown>
    try {
      invoice = JSON.parse(invoiceJson)
    } catch {
      setError("Invalid invoice JSON")
      return
    }
    setLoading(true)
    try {
      const res = await executeRules({ doc_id: docId, invoice })
      setResult(res)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-bold">Execute Rules</h1>
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="space-y-1">
            <Label>Doc ID</Label>
            <Input value={docId} onChange={e => setDocId(e.target.value)} placeholder="DOC-XXXXXXXX" />
          </div>
          <div className="space-y-1">
            <Label>Invoice JSON</Label>
            <textarea
              className="w-full h-40 rounded-md border border-input bg-background px-3 py-2 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
              value={invoiceJson}
              onChange={e => setInvoiceJson(e.target.value)}
              spellCheck={false}
            />
          </div>
          <Button onClick={run} disabled={loading || !docId}>
            {loading ? "Running…" : "Execute"}
          </Button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <DecisionBanner
          decision={result.decision}
          reasons={result.reasons}
          triggeredRuleIds={result.triggered_rule_ids}
        />
      )}
    </div>
  )
}
