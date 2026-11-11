import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const webRoot = path.dirname(fileURLToPath(import.meta.url));

const documentRoutes = ["/", "/about", "/vendors", "/enrollment", "/sources", "/methodology", "/dictionary", "/explore/:path*", "/lines/:path*"];

const nextConfig: NextConfig = {
  outputFileTracingRoot: webRoot,
  outputFileTracingIncludes: {
    "/*": ["./data/public/ledger.sqlite"],
    "/api/export": ["./data/public/ledger.sqlite"],
    "/sources": ["./data/public/ledger.sqlite"],
    "/lines/[id]": ["./data/public/ledger.sqlite"],
  },
  async headers() {
    return documentRoutes.map((source) => ({
      source,
      headers: [{ key: "Cache-Control", value: "private, no-store, max-age=0, must-revalidate" }],
    }));
  },
};

export default nextConfig;
