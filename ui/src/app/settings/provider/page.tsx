"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConfigEditor } from "@/components/ConfigEditor"
import {
  getProviderConfig, updateProviderConfig, listProviders, switchProvider,
  type ProviderConfigResponse, type ProviderListItem,
} from "@/lib/api"

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

const PROVIDER_LABELS: Record<string, string> = {
  openrouter: "OpenRouter",
  nvidia: "NVIDIA NIM",
  bedrock: "AWS Bedrock",
}

export default function ProviderSettingsPage() {
  const [provider, setProvider] = useState<ProviderConfigResponse | null>(null)
  const [allProviders, setAllProviders] = useState<ProviderListItem[]>([])
  const [switching, setSwitching] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getProviderConfig(), listProviders()])
      .then(([active, list]) => {
        setProvider(active)
        setAllProviders(list.providers)
      })
      .catch(e => setError(String(e)))
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

  async function onSwitch(providerId: string) {
    setSwitching(providerId)
    try {
      const updated = await switchProvider(providerId)
      setProvider(updated)
      const list = await listProviders()
      setAllProviders(list.providers)
    } catch (e) {
      setError(String(e))
    } finally {
      setSwitching(null)
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <h1 className="text-2xl font-bold">Provider Config</h1>

      <Card>
        <CardHeader>
          <CardTitle>Active Provider</CardTitle>
          <CardDescription>Select which LLM provider the pipeline uses</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {allProviders.map(p => (
            <div
              key={p.provider_id}
              className={`flex items-center justify-between rounded-md border px-4 py-3 ${
                p.is_active ? "border-primary bg-primary/5" : "border-border"
              }`}
            >
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-muted-foreground">{PROVIDER_LABELS[p.type] ?? p.type}</p>
              </div>
              {p.is_active ? (
                <span className="text-xs font-medium text-primary">Active</span>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={switching === p.provider_id}
                  onClick={() => onSwitch(p.provider_id)}
                >
                  {switching === p.provider_id ? "Switching…" : "Use this"}
                </Button>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

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
