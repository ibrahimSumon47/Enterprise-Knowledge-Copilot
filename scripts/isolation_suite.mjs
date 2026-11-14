#!/usr/bin/env node
/**
 * Cross-tenant red-team suite against the deployed API and real database.
 *
 * Two workspaces are created through POST /signup (the real sign-up path), each
 * owner adds one document through onboarding, then one tenant tries to read the
 * other through guessed ids, swapped org headers, a tampered token, library
 * search, audit and the unanswered queue. Leakage must be exactly zero.
 * Both workspaces and both auth users are deleted afterwards.
 */
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

const apiBase = (process.env.API_URL ?? "https://enterprise-knowledge-copilot-2u57.onrender.com").replace(/\/$/, "");
const supabaseUrl = (process.env.SUPABASE_URL ?? "").replace(/\/$/, "");
const anonKey = process.env.SUPABASE_ANON_KEY ?? "";
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";

if (!supabaseUrl || !anonKey || !serviceKey) {
  console.error("SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are required");
  process.exit(2);
}

const violations = [];
let checks = 0;

function expect(condition, message) {
  checks += 1;
  if (!condition) {
    violations.push(message);
    console.error(`LEAK ${message}`);
  }
}

async function json(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return { raw: text };
  }
}

async function call(path, token, init = {}) {
  return fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
}

async function signup(email, password) {
  const response = await call("/signup", null, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (response.status !== 201) {
    throw new Error(`signup ${response.status}: ${(await response.text()).slice(0, 200)}`);
  }
}

async function signin(email, password) {
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: anonKey, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await json(response);
  if (!response.ok || !data?.access_token) {
    throw new Error(`sign-in ${response.status}: ${JSON.stringify(data).slice(0, 200)}`);
  }
  return { token: data.access_token, userId: data.user.id };
}

async function service(path, init = {}) {
  const response = await fetch(`${supabaseUrl}/rest/v1${path}`, {
    ...init,
    headers: {
      apikey: serviceKey,
      Authorization: `Bearer ${serviceKey}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
      ...(init.headers ?? {}),
    },
  });
  const body = await json(response);
  if (!response.ok) throw new Error(`service ${path} ${response.status}: ${JSON.stringify(body)}`);
  return body;
}

async function workspace(token, title) {
  const me = await json(await call("/me", token));
  const orgId = me.org_id;
  if (!orgId) throw new Error("the signed-in owner has no workspace");
  const response = await call("/onboarding/document", token, {
    method: "POST",
    body: JSON.stringify({
      title,
      text: `${title}. This workspace keeps its own policies. Receipts are due within 45 days and approval above 25 USD is required.`,
    }),
  });
  if (!response.ok) {
    throw new Error(`first document ${response.status}: ${(await response.text()).slice(0, 200)}`);
  }
  return { title, orgId, ...me, ...(await json(response)) };
}

async function cleanup(state) {
  for (const item of state) {
    if (!item) continue;
    try {
      if (item.token) await call("/workspace", item.token, { method: "DELETE" });
    } catch (error) {
      console.error(`cleanup workspace failed: ${error.message}`);
    }
    try {
      if (item.userId) {
        await fetch(`${supabaseUrl}/auth/v1/admin/users/${item.userId}`, {
          method: "DELETE",
          headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}` },
        });
      }
    } catch (error) {
      console.error(`cleanup user failed: ${error.message}`);
    }
  }
}

async function waitForDeploy() {
  const expected = (process.env.COMMIT_SHA ?? "").slice(0, 7);
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const health = await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(45_000) });
      const specResponse = await fetch(`${apiBase}/openapi.json`, {
        signal: AbortSignal.timeout(45_000),
      });
      if (health.ok && specResponse.ok) {
        const build = await health.json();
        const spec = await specResponse.json();
        const commitReady = !expected || String(build.commit ?? "").startsWith(expected);
        if (
          commitReady &&
          spec.paths?.["/signup"] &&
          spec.paths?.["/workspace"]?.delete &&
          spec.paths?.["/documents/upload"]
        ) {
          return;
        }
      }
    } catch {
      /* keep waiting for Render */
    }
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
  throw new Error("the deployed API has not reached this commit yet");
}

async function main() {
  await waitForDeploy();
  const stamp = Date.now();
  const accounts = [
    { email: `isolation-a-${stamp}@ekc-e2e.test`, password: `Ekc-a-${randomUUID()}` },
    { email: `isolation-b-${stamp}@ekc-e2e.test`, password: `Ekc-b-${randomUUID()}` },
  ];
  const state = [];
  try {
    for (const account of accounts) {
      await signup(account.email, account.password);
      const session = await signin(account.email, account.password);
      state.push({ ...account, ...session });
    }
    const [a, b] = state;
    a.workspace = await workspace(a.token, `Tenant A private note ${stamp}`);
    b.workspace = await workspace(b.token, `Tenant B secret note ${stamp}`);

    // Library: A must not see B's document title or id.
    const library = await json(await call("/documents", a.token));
    const titles = (library.documents ?? []).map((doc) => doc.title);
    expect(!titles.includes(b.workspace.title), "library exposed tenant B document");
    expect(titles.includes(a.workspace.title), "tenant A cannot see its own document");

    // Swapped headers cannot change the tenant.
    const swapped = await json(
      await call("/documents", a.token, { headers: { "X-Org-Id": b.workspace.orgId, "X-Organisation": b.workspace.orgId } }),
    );
    const swappedTitles = (swapped.documents ?? []).map((doc) => doc.title);
    expect(!swappedTitles.includes(b.workspace.title), "X-Org-Id header switched the tenant");

    // Search/recall must stay inside the org.
    const recall = await json(
      await call(`/admin/recall?question=${encodeURIComponent("receipts approval")}&k=50`, a.token),
    );
    const recallTitles = (recall.candidates ?? []).map((row) => row.title);
    expect(!recallTitles.includes(b.workspace.title), "retrieval returned tenant B passage");

    // Upload attacks: wrong type renamed, oversized, path traversal, zip bomb
    // and another tenant's document id.
    async function upload(token, filename, bytes, type) {
      const body = new FormData();
      body.set("file", new Blob([bytes], { type }), filename);
      // No explicit Content-Type: fetch must add the multipart boundary.
      const response = await fetch(`${apiBase}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body,
      });
      return response;
    }

    const renamed = await upload(
      a.token,
      "policy.pdf",
      "this is plain text, not a pdf",
      "application/pdf",
    );
    expect(renamed.status === 400, `renamed PDF returned ${renamed.status}`);

    const oversized = await upload(
      a.token,
      "larger.txt",
      new Uint8Array(10 * 1024 * 1024 + 1).fill(97),
      "text/plain",
    );
    expect(oversized.status === 413, `oversized upload returned ${oversized.status}`);

    const traversal = await upload(
      a.token,
      "../../etc/passwd.txt",
      "Path traversal fixture. Receipts are due within 45 days and approval is required.",
      "text/plain",
    );
    // Cloudflare may block the traversal payload before Render sees it; either
    // the edge rejects it or the API sanitises and accepts it.
    expect(
      [202, 400, 403].includes(traversal.status),
      `path-traversal upload returned ${traversal.status}`,
    );

    const bomb = await upload(
      a.token,
      "bomb.docx",
      readFileSync(new URL("../e2e/fixtures/bomb.docx", import.meta.url)),
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(
      [400, 422].includes(bomb.status),
      `zip-bomb DOCX returned ${bomb.status}`,
    );

    const foreignDocument = await call(`/documents/${a.workspace.document_id}`, b.token);
    expect(foreignDocument.status === 404, `foreign document id returned ${foreignDocument.status}`);

    // A shared answer link guessed by B is not found.
    const [conversation] = await service("/conversations", {
      method: "POST",
      body: JSON.stringify({
        org_id: a.workspace.orgId,
        user_id: a.userId,
        title: "Shared link target",
      }),
    });
    const guessed = await call(`/conversations/${conversation.id}/messages`, b.token);
    expect(guessed.status === 404, `guessed conversation id returned ${guessed.status}`);

    // A tampered token is rejected before any membership lookup.
    const tampered = `${a.token.slice(0, -4)}beef`;
    const forged = await call("/me", tampered);
    expect(forged.status === 401, `tampered token returned ${forged.status}`);

    // Audit read: B's onboarding action must not appear.
    const audit = await json(await call("/audit?limit=200", a.token));
    const auditText = JSON.stringify(audit);
    expect(!auditText.includes(b.workspace.title), "audit leaked tenant B document title");

    // Unanswered queue: insert a real B row, then read A's queue.
    const question = `Tenant B unanswered ${stamp}`;
    await service("/unanswered_questions", {
      method: "POST",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify({
        org_id: b.workspace.orgId,
        user_id: b.userId,
        role: "owner",
        question,
        reason: "no evidence",
        closest: [],
      }),
    });
    const queue = await json(await call("/admin/unanswered?limit=200", a.token));
    expect(!JSON.stringify(queue).includes(question), "unanswered queue leaked tenant B question");

    console.log(`checks=${checks} violations=${violations.length}`);
    if (violations.length > 0) process.exitCode = 1;
  } finally {
    await cleanup(state);
  }
}

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exit(1);
});
