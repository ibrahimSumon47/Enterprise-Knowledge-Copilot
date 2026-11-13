#!/usr/bin/env node
/**
 * Blocks until the deployed web app serves the build that contains the current
 * change. Vercel deploys asynchronously, so an end-to-end workflow that starts
 * on push must wait for the marker instead of sleeping a guessed number of
 * seconds.
 */
const url = process.env.EKC_WEB_URL ?? "https://enterprise-knowledge-copilot-wine.vercel.app";
const marker = process.env.EKC_DEPLOY_MARKER ?? 'data-auth-version="3"';
const deadline = Date.now() + 10 * 60_000;

while (Date.now() < deadline) {
  try {
    const response = await fetch(`${url}/login`, { cache: "no-store" });
    const html = await response.text();
    if (response.ok && html.includes(marker)) {
      console.log(`deployed build is live: ${marker}`);
      process.exit(0);
    }
    console.log(`waiting for ${marker} (HTTP ${response.status})`);
  } catch (error) {
    console.log(`waiting for ${url}: ${error instanceof Error ? error.message : "unreachable"}`);
  }
  await new Promise((resolve) => setTimeout(resolve, 15_000));
}

console.error(`the deployed build did not serve ${marker} within 10 minutes`);
process.exit(1);
