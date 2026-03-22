import type { Metadata } from 'next'
import './globals.css'
import { Sidebar } from '@/components/Sidebar'

export const metadata: Metadata = {
  title: 'PolyClaw Trading Dashboard',
  description: 'Fintech dashboard for Polymarket trading monitoring and analytics',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 ml-[240px] p-6 overflow-y-auto min-h-screen">
          {children}
        </main>
      </body>
    </html>
  )
}
