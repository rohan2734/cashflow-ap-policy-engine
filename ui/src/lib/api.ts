const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type UploadResponse = { doc_id: string; rule_count: number; conflict_count: number }
export type RuleResponse = { rule_id: string; action: string; confidence: number; source_clauses: string[]; condition: object }
export type RulesListResponse = { doc_id: string; rules: RuleResponse[] }
export type ExecuteRequest = { doc_id: string; invoice: Record<string, unknown> }
export type ExecuteResponse = { decision: string; triggered_rule_ids: string[]; reasons: string[] }
export type ReviewRuleResponse = {
  rule_id: string; doc_id: string; action: string; confidence: number
  source_clauses: string[]; condition: object; status: string; override_action: string | null
}
export type ReviewQueueResponse = { rules: ReviewRuleResponse[] }
export type PipelineConfigResponse = { pipeline_id: string; name: string; config: Record<string, unknown> }
export type ProviderConfigResponse = { provider_id: string; name: string; type: string; config: Record<string, unknown> }
export type ProviderListItem = { provider_id: string; name: string; type: string; config: Record<string, unknown>; is_active: boolean }
export type ProvidersListResponse = { providers: ProviderListItem[] }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function uploadPolicy(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", file)
  return request("/upload", { method: "POST", body: form })
}

export async function getRules(docId: string): Promise<RulesListResponse> {
  return request(`/rules/${docId}`)
}

export async function executeRules(req: ExecuteRequest): Promise<ExecuteResponse> {
  return request("/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}

export async function getReviewQueue(): Promise<ReviewQueueResponse> {
  return request("/review")
}

export async function patchRule(ruleId: string, overrideAction: string): Promise<ReviewRuleResponse> {
  return request(`/rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ override_action: overrideAction }),
  })
}

export async function getReviewThreshold(): Promise<{ threshold: number }> {
  return request("/settings/review-threshold")
}

export async function setReviewThreshold(threshold: number): Promise<{ threshold: number }> {
  return request("/settings/review-threshold", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ threshold }),
  })
}

export async function getPipelineConfig(): Promise<PipelineConfigResponse> {
  return request("/config/pipeline")
}

export async function updatePipelineConfig(config: Record<string, unknown>): Promise<PipelineConfigResponse> {
  return request("/config/pipeline", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  })
}

export async function getProviderConfig(): Promise<ProviderConfigResponse> {
  return request("/config/provider")
}

export async function updateProviderConfig(config: Record<string, unknown>): Promise<ProviderConfigResponse> {
  return request("/config/provider", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  })
}

export async function listProviders(): Promise<ProvidersListResponse> {
  return request("/config/providers")
}

export async function switchProvider(providerId: string): Promise<ProviderConfigResponse> {
  return request(`/config/provider/${providerId}`, { method: "PUT" })
}
