import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Codebase Intelligence",
  description: "Analyze and understand any public GitHub repository.",
}

export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>
}
