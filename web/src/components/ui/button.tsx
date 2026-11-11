import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export function ButtonLink({
  href,
  children,
  variant = "solid",
}: {
  href: string;
  children: ReactNode;
  variant?: "solid" | "ghost";
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
        variant === "solid"
          ? "bg-copper text-white hover:bg-copper/90 focus-visible:outline-copper"
          : "border border-ink/15 bg-white text-ink hover:bg-paper",
      )}
    >
      {children}
    </Link>
  );
}
