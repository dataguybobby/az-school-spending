import type { Metadata } from "next";
import { Source_Sans_3, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Source_Sans_3({ subsets: ["latin"], variable: "--font-sans-body" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--font-serif-display" });

export const metadata: Metadata = {
  title: "Metro School Ledger",
  description: "Reported public K-12 accounts payable and voucher lines for the Phoenix area.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${serif.variable} font-sans antialiased`}>
        <header className="border-b border-ink/10 bg-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-3 px-4 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-copper">Read-only public extract</p>
              <Link href="/" className="font-serif text-2xl font-semibold text-ink">
                Metro School Ledger
              </Link>
            </div>
            <nav className="flex gap-4 text-sm font-semibold">
              <Link href="/" className="hover:text-copper">Spending</Link>
              <Link href="/sources" className="hover:text-copper">Sources</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
