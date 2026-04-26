import type { Metadata } from "next"
import Link from "next/link"
import "./globals.css"

export const metadata: Metadata = {
  title: "CashFlo — Policy-to-Rule Engine",
  description: "Upload procurement policies, extract structured rules, execute against invoices",
}

const NAV_LINKS = [
  { href: "/upload", label: "Upload" },
  { href: "/review", label: "Review Queue" },
  { href: "/execute", label: "Execute" },
  { href: "/settings", label: "Settings" },
]

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans antialiased">
        <header className="border-b">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">
            <Link href="/" className="font-bold text-lg tracking-tight">CashFlo</Link>
            <nav className="flex gap-4 text-sm text-muted-foreground">
              {NAV_LINKS.map(l => (
                <Link key={l.href} href={l.href} className="hover:text-foreground transition-colors">
                  {l.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  )
}
