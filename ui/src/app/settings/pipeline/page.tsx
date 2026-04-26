"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { ConfigEditor } from "@/components/ConfigEditor"
import { getPipelineConfig, updatePipelineConfig } from "@/lib/api"

export default function PipelineSettingsPage() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPipelineConfig()
      .then(r => setConfig(r.config))
      .catch(e => setError(String(e)))
  }, [])

  if (error) return <p className="text-red-600">{error}</p>
  if (!config) return <p className="text-muted-foreground">Loading…</p>

  return (
    <div className="max-w-lg space-y-4">
      <h1 className="text-2xl font-bold">Pipeline Config</h1>
      <Card>
        <CardHeader>
          <CardTitle>Active Pipeline</CardTitle>
          <CardDescription>
            Edit <code>confidence_threshold</code>, <code>concurrency</code>, and <code>notification_endpoint</code>.
            Changes take effect immediately.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ConfigEditor
            label="Pipeline JSONB config"
            initialConfig={config}
            onSave={async cfg => {
              const res = await updatePipelineConfig(cfg)
              setConfig(res.config)
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}
