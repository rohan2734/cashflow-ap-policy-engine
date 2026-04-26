import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

const PAGES = [
  { href: "/upload", title: "Upload Policy", description: "Upload a PDF and extract rules via LLM" },
  { href: "/review", title: "Review Queue", description: "Human-review low-confidence rules" },
  { href: "/execute", title: "Execute", description: "Run extracted rules against an invoice" },
  { href: "/settings", title: "Settings", description: "Configure threshold, pipeline, and provider" },
]

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">CashFlo Policy Engine</h1>
        <p className="text-muted-foreground mt-1">Upload procurement policies, extract structured rules, execute against invoices.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {PAGES.map(p => (
          <Card key={p.href}>
            <CardHeader>
              <CardTitle>{p.title}</CardTitle>
              <CardDescription>{p.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild><Link href={p.href}>Open</Link></Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
