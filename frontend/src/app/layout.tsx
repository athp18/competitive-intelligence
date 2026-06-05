import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Intelligence",
  description: "Competitive intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`min-h-screen font-[family-name:var(--font-inter)]`}>
        <nav className="border-b border-white/[0.06] px-6 py-3.5 flex items-center justify-between">
          <span className="text-sm font-medium text-white tracking-tight">Intelligence</span>
          <span className="text-xs text-white/20">competitive intelligence</span>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
