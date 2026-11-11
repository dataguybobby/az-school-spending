import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const repoRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  outputFileTracingRoot: repoRoot,
  outputFileTracingIncludes: {
    "/*": ["./data/public/ledger.sqlite"],
    "/api/export": ["./data/public/ledger.sqlite"],
    "/sources": ["./data/public/ledger.sqlite"],
    "/lines/[id]": ["./data/public/ledger.sqlite"],
  },
};

export default nextConfig;
