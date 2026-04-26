import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ThresholdSlider } from "@/components/ThresholdSlider"

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Review Threshold</CardTitle>
          <CardDescription>Rules below this confidence are queued for human review.</CardDescription>
        </CardHeader>
        <CardContent>
          <ThresholdSlider />
        </CardContent>
      </Card>
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline Config</CardTitle>
            <CardDescription className="text-xs">Concurrency, threshold, notification endpoint.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm"><Link href="/settings/pipeline">Edit →</Link></Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Provider Config</CardTitle>
            <CardDescription className="text-xs">LLM model, temperature, API keys.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm"><Link href="/settings/provider">Edit →</Link></Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
