import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "api/**",
      "docs/**",
      "scripts/**",
      "coverage/**",
      ".corpus-src/**",
      "data/**",
    ],
  },
  ...nextVitals,
  ...nextTs,
];

export default config;
