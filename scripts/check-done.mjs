#!/usr/bin/env node
/**
 * Phase gate. Every check prints its evidence; nothing passes on faith.
 *
 *   node scripts/check-done.mjs            # every phase
 *   node scripts/check-done.mjs --phase P4 # one phase
 *
 * Exit code 0 only when every selected check passes.
 */

import { readFileSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const args = process.argv.slice(2);
const phaseIndex = args.indexOf("--phase");
const only = phaseIndex >= 0 ? args[phaseIndex + 1]?.toUpperCase() : null;

const read = (path) => (existsSync(join(root, path)) ? readFileSync(join(root, path), "utf8") : "");
const has = (path) => existsSync(join(root, path));
const lines = (path) => read(path).split("\n").filter((line) => line.trim()).length;
const bytes = (path) => (has(path) ? statSync(join(root, path)).size : 0);

const fileCheck = (label, path) => ({
  label,
  run: () => ({ ok: has(path), evidence: has(path) ? `${path} (${bytes(path)} B)` : `${path} missing` }),
});

const containsCheck = (label, path, needles) => ({
  label,
  run: () => {
    const text = read(path);
    const missing = needles.filter((needle) => !text.includes(needle));
    return {
      ok: missing.length === 0,
      evidence: missing.length === 0 ? `${path} contains ${needles.length} markers` : `${path} lacks: ${missing.join(", ")}`,
    };
  },
});

const minLinesCheck = (label, path, minimum) => ({
  label,
  run: () => {
    const count = lines(path);
    return { ok: count >= minimum, evidence: `${path} has ${count} lines (need ${minimum})` };
  },
});

const urlCheck = (label, url) => ({
  label,
  run: async () => {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(20000) });
      return { ok: response.ok, evidence: `${url} -> ${response.status}` };
    } catch (error) {
      return { ok: false, evidence: `${url} -> ${error instanceof Error ? error.message : "unreachable"}` };
    }
  },
});

const phases = {
  P0: [
    fileCheck("agent contract", "AGENTS.md"),
    fileCheck("project state", "docs/PROJECT_STATE.md"),
    fileCheck("feature ledger", "docs/features.json"),
    fileCheck("security policy", "SECURITY.md"),
    fileCheck("phase gate", "scripts/check-done.mjs"),
    containsCheck("commit hygiene gate", ".github/workflows/ci.yml", ["Co-Authored-By", "commit-hygiene"]),
  ],
  P1: [
    containsCheck("schema defines the access predicate", "supabase/migrations/20261111000100_init.sql", [
      "create or replace function public.can_read",
      "search_chunks",
      "vector(384)",
    ]),
    containsCheck("row level security is enabled", "supabase/migrations/20261111000100_init.sql", [
      "enable row level security",
      "policy",
    ]),
  ],
  P2: [
    fileCheck("corpus file", "data/corpus.jsonl"),
    minLinesCheck("corpus size", "data/corpus.jsonl", 700),
    containsCheck("synthetic documents are labelled", "data/corpus.jsonl", ['"is_synthetic": true']),
  ],
  P3: [
    containsCheck("api routes", "api/app/main.py", ["/chat", "/chat/stream", "/admin/ingest", "/audit/verify"]),
    containsCheck("citation verification", "api/app/pipeline.py", ["verify_answer", "REFUSAL"]),
    fileCheck("api tests", "api/tests/test_units.py"),
  ],
  P4: [
    fileCheck("app shell", "app/layout.tsx"),
    fileCheck("sign-in page", "app/login/page.tsx"),
    fileCheck("chat page", "app/chat/page.tsx"),
    fileCheck("design tokens", "app/globals.css"),
  ],
  P5: [
    fileCheck("golden set", "eval/golden_set.jsonl"),
    minLinesCheck("golden set size", "eval/golden_set.jsonl", 80),
    containsCheck("leakage gate", "eval/run_eval.py", ["leak"]),
  ],
  P6: [
    fileCheck("threat model", "docs/THREAT_MODEL.md"),
    fileCheck("security report", "docs/reports/security.md"),
    fileCheck("security.txt", "public/.well-known/security.txt"),
  ],
  P7: [
    urlCheck("web is live", "https://enterprise-knowledge-copilot-wine.vercel.app/"),
    urlCheck("api health", "https://enterprise-knowledge-copilot-2u57.onrender.com/health"),
  ],
  P8: [
    fileCheck("evaluation report", "docs/reports/eval.json"),
    fileCheck("gold published", "docs/reports/gold.json"),
  ],
  P9: [
    fileCheck("project facts", "docs/PROJECT_FACTS.json"),
    fileCheck("llms.txt", "public/llms.txt"),
    fileCheck("runbook", "docs/RUNBOOK.md"),
    fileCheck("decision records", "docs/adr/0001-stack.md"),
  ],
};

const selected = only ? [[only, phases[only]]] : Object.entries(phases);
if (only && !phases[only]) {
  console.error(`Unknown phase: ${only}. Known: ${Object.keys(phases).join(", ")}`);
  process.exit(2);
}

let failures = 0;
for (const [phase, checks] of selected) {
  console.log(`\n${phase}`);
  for (const check of checks) {
    const result = await check.run();
    if (!result.ok) failures += 1;
    console.log(`  ${result.ok ? "DONE    " : "MISSING "} ${check.label} — ${result.evidence}`);
  }
}

console.log(
  failures === 0
    ? `\nAll checks passed${only ? ` for ${only}` : ""}.`
    : `\n${failures} check(s) not done. Fix the cause; do not lower the gate.`,
);
process.exit(failures === 0 ? 0 : 1);
