"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"

interface ConfigEditorProps {
  label: string
  initialConfig: Record<string, unknown>
  onSave: (config: Record<string, unknown>) => Promise<void>
}

export function ConfigEditor({ label, initialConfig, onSave }: ConfigEditorProps) {
  const [raw, setRaw] = useState(JSON.stringify(initialConfig, null, 2))
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error" | "invalid">("idle")

  async function save() {
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(raw)
    } catch {
      setStatus("invalid")
      return
    }
    setStatus("saving")
    try {
      await onSave(parsed)
      setStatus("saved")
    } catch {
      setStatus("error")
    }
  }

  return (
    <div className="space-y-3">
      <Label>{label}</Label>
      <textarea
        className="w-full h-64 rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
        value={raw}
        onChange={e => { setRaw(e.target.value); setStatus("idle") }}
        spellCheck={false}
      />
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={status === "saving"}>
          {status === "saving" ? "Saving…" : "Save"}
        </Button>
        {status === "saved" && <span className="text-sm text-green-600">Saved</span>}
        {status === "error" && <span className="text-sm text-red-600">Failed to save</span>}
        {status === "invalid" && <span className="text-sm text-red-600">Invalid JSON</span>}
      </div>
    </div>
  )
}
