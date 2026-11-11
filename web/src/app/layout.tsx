import type { Metadata } from "next";
import { Nunito } from "next/font/google";
import Image from "next/image";
import Link from "next/link";
import "./globals.css";

const nunito = Nunito({
  subsets: ["latin"],
  weight: ["400", "600", "800"],
  variable: "--font-nunito",
  display: "swap",
});

const description =
  "Reported public K-12 accounts payable and voucher lines. Phoenix Dataworks publishes this site. It is not an official government site, not a census, and not proof a payment settled.";

export const metadata: Metadata = {
  title: {
    default: "AZ School Spending",
    template: "%s · AZ School Spending",
  },
  description,
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/az-school-spending-logo-square-1024.png", sizes: "1024x1024", type: "image/png" },
    ],
    apple: [{ url: "/az-school-spending-logo-square-1024.png", sizes: "1024x1024" }],
  },
  openGraph: {
    title: "AZ School Spending",
    description,
    images: [
      {
        url: "/az-school-spending-logo-wide-1200x630.png",
        width: 1200,
        height: 630,
        alt: "AZ School Spending",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AZ School Spending",
    description,
    images: ["/az-school-spending-logo-wide-1200x630.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${nunito.variable} ${nunito.className} antialiased`}>
        <header className="border-b border-teal/15 bg-cream">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="flex items-center gap-3">
              <Image
                src="/az-school-spending-logo-wide-1800x600.png"
                alt="AZ School Spending"
                width={1800}
                height={600}
                priority
                className="hidden h-16 w-auto md:block"
              />
              <span className="flex items-center gap-2 md:hidden">
                <Image
                  src="/az-school-spending-mark-1024-transparent.png"
                  alt=""
                  width={1024}
                  height={1024}
                  priority
                  className="h-11 w-11"
                />
                <span className="wordmark text-lg leading-tight text-teal">AZ School Spending</span>
              </span>
            </Link>
            <nav className="flex flex-wrap gap-4 text-sm font-semibold text-teal">
              <Link href="/" className="hover:text-terracotta">Spending</Link>
              <Link href="/explore" className="hover:text-terracotta">Groups</Link>
              <Link href="/sources" className="hover:text-terracotta">Sources</Link>
              <Link href="/methodology" className="hover:text-terracotta">Methodology</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="border-t border-teal/15">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-6 text-sm">
            <Image
              src="/az-school-spending-logo-square-1024.png"
              alt=""
              width={1024}
              height={1024}
              className="h-10 w-10"
            />
            <Link href="/methodology" className="font-semibold text-teal underline">Methodology</Link>
            <span className="text-teal/75">Phoenix Dataworks publishes AZ School Spending. Not an official government site. Reported and vouchered amounts, not settlement proof.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
