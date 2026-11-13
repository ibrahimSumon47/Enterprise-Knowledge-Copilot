import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/trust", destination: "/security", permanent: true },
      { source: "/credits", destination: "/licenses", permanent: true },
      { source: "/evals", destination: "/admin/quality", permanent: true },
      { source: "/traces", destination: "/admin/quality", permanent: true },
      { source: "/audit", destination: "/admin", permanent: true },
    ];
  },
};

export default nextConfig;
