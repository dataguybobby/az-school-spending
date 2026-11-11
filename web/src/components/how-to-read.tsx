import Link from "next/link";

export function HowToRead({ anchor = "caveats" }: { anchor?: string }) {
  return (
    <Link className="font-semibold text-teal underline" href={`/methodology#${anchor}`}>
      How to read this
    </Link>
  );
}
