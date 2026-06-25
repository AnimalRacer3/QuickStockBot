import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // outputFileTracingRoot silences the monorepo lockfile warning in next lint / next build
  outputFileTracingRoot: require("path").join(__dirname, "../../"),
};

export default nextConfig;
