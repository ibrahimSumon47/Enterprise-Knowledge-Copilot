// Public origin of the FastAPI service. The env var wins when it is set;
// the fallback keeps the deployed preview working without extra setup.
const RENDER_API_BASE_URL = "https://enterprise-knowledge-copilot-2u57.onrender.com";

export const site = {
  name: "Enterprise Knowledge Copilot",
  shortName: "EKC",
  tagline: "Ask the handbook. Get answers with proof.",
  description:
    "A role-aware copilot over a real company handbook: answers with citations, honest refusals, server-side access control and a tamper-evident audit trail.",
  url: "https://enterprise-knowledge-copilot-wine.vercel.app",
  repo: "https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot",
  handbook: {
    title: "GitLab Handbook",
    url: "https://handbook.gitlab.com/",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
  },
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? RENDER_API_BASE_URL,
} as const;

/** Roles the access model knows about, in the order they appear in the UI. */
export const ROLES = [
  "guest",
  "employee",
  "engineering",
  "security",
  "hr",
  "finance",
  "admin",
] as const;

export type Role = (typeof ROLES)[number];

export const ACCESS_LEVELS = ["public", "employee", "department", "confidential"] as const;
export type AccessLevel = (typeof ACCESS_LEVELS)[number];

export const ROLE_LABEL: Record<Role, string> = {
  guest: "Guest / contractor",
  employee: "Employee",
  engineering: "Engineering",
  security: "Security analyst",
  hr: "HR partner",
  finance: "Finance",
  admin: "Administrator",
};

export const DEPARTMENT_OF_ROLE: Partial<Record<Role, string>> = {
  engineering: "engineering",
  security: "security",
  hr: "people",
  finance: "finance",
};

export function visibleLevels(role: Role): AccessLevel[] {
  if (role === "admin") return [...ACCESS_LEVELS];
  if (role === "guest") return ["public"];
  return ["public", "employee"];
}
