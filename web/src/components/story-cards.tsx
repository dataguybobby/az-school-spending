import Link from "next/link";
import { dollars } from "@/lib/utils";

type Story = {
  line_id: string;
  amount_cents: number;
  vendor_raw: string;
  description_public: string;
  entity_name: string;
  check_date: string | null;
  voucher_batch_date: string | null;
  dac_raw: string | null;
};

export function StoryCards({ stories }: { stories: Story[] }) {
  if (stories.length === 0) return null;
  return (
    <section>
      <h2 className="font-serif text-2xl">Lines you can open</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-ink/70">
        Each card is one screened public line. It is not a finding, not proof a payment settled, and not the whole vendor or district.
      </p>
      <ul className="mt-4 grid gap-3 md:grid-cols-3">
        {stories.map((story) => (
          <li key={story.line_id} className="story-card rounded-xl border border-ink/10 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-copper">Screened line</p>
            <p className="mt-2 font-serif text-3xl">{dollars(story.amount_cents)}</p>
            <p className="mt-2 text-sm font-semibold leading-5">{story.description_public}</p>
            <p className="mt-2 text-sm text-ink/75">{story.vendor_raw}</p>
            <p className="mt-1 text-xs text-ink/55">
              {story.entity_name}
              {story.dac_raw ? ` · ${story.dac_raw}` : ""}
              {" · "}
              {story.check_date ? `check date ${story.check_date}` : story.voucher_batch_date ? `voucher batch date ${story.voucher_batch_date}` : "no confirmed date on this line"}
            </p>
            <Link className="mt-3 inline-block text-sm font-semibold text-copper underline" href={`/lines/${story.line_id}`}>
              Open this line
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
