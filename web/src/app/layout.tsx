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
            <nav className="flex flex-wrap gap-4 text-sm font-semibold">
              <Link href="/" className="hover:text-copper">Spending</Link>
              <Link href="/explore" className="hover:text-copper">Groups</Link>
              <Link href="/sources" className="hover:text-copper">Sources</Link>
              <Link href="/methodology" className="hover:text-copper">Methodology</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="border-t border-ink/10">
          <div className="mx-auto flex max-w-6xl flex-wrap gap-4 px-4 py-6 text-sm">
            <Link href="/methodology" className="font-semibold text-copper underline">Methodology</Link>
            <span className="text-ink/70">Phoenix Dataworks. Not an official government site. Reported and vouchered amounts, not settlement proof.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
