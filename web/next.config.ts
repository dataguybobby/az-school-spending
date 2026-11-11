import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingIncludes: {
    "/*": ["./data/public/ledger.sqlite"],
    "/api/export": ["./data/public/ledger.sqlite"],
    "/sources": ["./data/public/ledger.sqlite"],
    "/lines/[id]": ["./data/public/ledger.sqlite"],
  },
};

export default nextConfig;
