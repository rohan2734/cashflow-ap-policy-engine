"use client"

import { useEffect, useState } from "react"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { getReviewThreshold, setReviewThreshold } from "@/lib/api"

export function ThresholdSlider() {
  const [value, setValue] = useState(0.5)
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")

  useEffect(() => {
    getReviewThreshold().then(r => setValue(r.threshold)).catch(() => {})
  }, [])

  async function save() {
    setStatus("saving")
    try {
      await setReviewThreshold(value)
      setStatus("saved")
    } catch {
      setStatus("error")
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <Label>Confidence Threshold</Label>
        <p className="text-sm text-muted-foreground mt-1">
          Rules extracted with confidence below this value will be queued for human review.
        </p>
      </div>
      <div className="flex items-center gap-4">
        <Slider
          min={0} max={1} step={0.05}
          value={[value]}
          onValueChange={([v]) => setValue(v)}
          className="flex-1"
        />
        <Input
          type="number" min={0} max={1} step={0.05}
          value={value}
          onChange={e => setValue(Number(e.target.value))}
          className="w-24"
        />
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={status === "saving"}>
          {status === "saving" ? "Saving…" : "Save"}
        </Button>
        {status === "saved" && <span className="text-sm text-green-600">Saved</span>}
        {status === "error" && <span className="text-sm text-red-600">Failed to save</span>}
      </div>
    </div>
  )
}
