import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <article className="space-y-6 text-base leading-7">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-teal">Phoenix Dataworks</p>
        <h1 className="mt-2 font-extrabold text-4xl">About</h1>
      </header>
      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <p>
          Phoenix Dataworks publishes AZ School Spending. This is not an official government site, and it is not a district or state report.
        </p>
        <p className="mt-3">
          The index covers administrative Maricopa and Pinal districts that have been indexed, from July 2024 onward. Amounts are reported / vouchered.
        </p>
        <p className="mt-3">
          <Link className="font-semibold text-teal underline" href="/methodology">Methodology</Link>
          {" · "}
          <Link className="font-semibold text-teal underline" href="/methodology#caveats">Caveats & how to read this data</Link>
          {" · "}
          <Link className="font-semibold text-teal underline" href="/sources">Sources</Link>
        </p>
      </section>
    </article>
  );
}
