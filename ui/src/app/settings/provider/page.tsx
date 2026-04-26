"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConfigEditor } from "@/components/ConfigEditor"
import { getProviderConfig, updateProviderConfig, type ProviderConfigResponse } from "@/lib/api"

const MODELS: Record<string, { label: string; group: string }[]> = {
  openrouter: [
    { label: "Llama 3 8B Instruct (default — extraction)", group: "Extraction" },
    { label: "Mixtral 8x7B Instruct", group: "RAG / Reasoning" },
    { label: "Llama 3 70B Instruct", group: "RAG / Reasoning" },
  ],
  nvidia: [{ label: "meta/llama-3-8b-instruct", group: "NVIDIA" }],
  bedrock: [{ label: "anthropic.claude-3-haiku-20240307-v1:0", group: "Bedrock" }],
}

const MODEL_IDS: Record<string, string[]> = {
  openrouter: ["meta-llama/llama-3-8b-instruct", "mistralai/mixtral-8x7b-instruct", "meta-llama/llama-3-70b-instruct"],
  nvidia: ["meta/llama-3-8b-instruct"],
  bedrock: ["anthropic.claude-3-haiku-20240307-v1:0"],
}

export default function ProviderSettingsPage() {
  const [provider, setProvider] = useState<ProviderConfigResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getProviderConfig().then(setProvider).catch(e => setError(String(e)))
  }, [])

  if (error) return <p className="text-red-600">{error}</p>
  if (!provider) return <p className="text-muted-foreground">Loading…</p>

  const providerType = provider.type
  const models = MODELS[providerType] ?? []
  const modelIds = MODEL_IDS[providerType] ?? []

  async function onModelChange(modelId: string) {
    if (!provider) return
    const updated = await updateProviderConfig({ ...provider.config, model: modelId })
    setProvider(updated)
  }

  return (
    <div className="max-w-lg space-y-4">
      <h1 className="text-2xl font-bold">Provider Config</h1>
      <Card>
        <CardHeader>
          <CardTitle>{provider.name}</CardTitle>
          <CardDescription>Type: <code>{providerType}</code></CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label>Model</Label>
            <Select
              value={String(provider.config.model ?? "")}
              onValueChange={onModelChange}
            >
              <SelectTrigger><SelectValue placeholder="Select model" /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Available Models</SelectLabel>
                  {modelIds.map((id, i) => (
                    <SelectItem key={id} value={id}>
                      {models[i]?.label ?? id}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <ConfigEditor
            label="Full provider JSONB config"
            initialConfig={provider.config}
            onSave={async cfg => {
              const res = await updateProviderConfig(cfg)
              setProvider(res)
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}
