"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { uploadPolicy, type UploadResponse } from "@/lib/api"

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<UploadResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleUpload() {
    const file = inputRef.current?.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const res = await uploadPolicy(file)
      setResult(res)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-bold">Upload Policy</h1>
      <Card>
        <CardContent className="pt-6 space-y-4">
          <input ref={inputRef} type="file" accept=".pdf" className="block w-full text-sm" />
          <Button onClick={handleUpload} disabled={loading}>
            {loading ? "Processing…" : "Upload & Extract"}
          </Button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader><CardTitle>Extraction Complete</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Doc ID: <span className="font-mono font-semibold">{result.doc_id}</span></p>
            <p>Rules extracted: <strong>{result.rule_count}</strong></p>
            <p>Conflicts detected: <strong>{result.conflict_count}</strong></p>
            <Button asChild variant="outline" className="mt-2">
              <Link href={`/rules/${result.doc_id}`}>View Rules →</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
