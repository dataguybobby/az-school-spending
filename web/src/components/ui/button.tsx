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
          ? "bg-terracotta text-white hover:bg-terracotta/90 focus-visible:outline-terracotta"
          : "border border-teal/15 bg-page text-teal hover:bg-cream",
      )}
    >
      {children}
    </Link>
  );
}
