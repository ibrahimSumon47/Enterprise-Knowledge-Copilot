import { z } from "zod";

import { site } from "./site";

const base = site.apiBaseUrl;

export const citationSchema = z.object({
  id: z.number(),
  title: z.string(),
  heading: z.string().nullable().optional(),
  document_id: z.string(),
  chunk_id: z.string(),
  snippet: z.string(),
  source_url: z.string().nullable().optional(),
  license: z.string(),
  attribution: z.string(),
  access_level: z.string(),
  is_synthetic: z.boolean().optional(),
  score: z.number(),
});

export type Citation = z.infer<typeof citationSchema>;

export const messageSchema = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  citations: z.array(citationSchema).default([]),
  confidence: z.enum(["high", "medium", "refused"]).nullable().optional(),
  refused: z.boolean().default(false),
  latency_ms: z.number().nullable().optional(),
  token_count: z.number().nullable().optional(),
  provider: z.string().nullable().optional(),
  created_at: z.string(),
});

export type ChatMessage = z.infer<typeof messageSchema>;

export const meSchema = z.object({
  id: z.string(),
  email: z.string(),
  role: z.string(),
  department: z.string().nullable(),
  visible_levels: z.array(z.string()),
});

export type Me = z.infer<typeof meSchema>;

export function apiConfigured(): boolean {
  return Boolean(base);
}

export async function apiFetch<T>(
  path: string,
  token: string,
  init: RequestInit = {},
  schema?: z.ZodType<T>,
): Promise<T> {
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured");
  const response = await fetch(`${base.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`API ${response.status}: ${detail.slice(0, 180)}`);
  }
  const data = await response.json();
  return schema ? schema.parse(data) : (data as T);
}

/** Parses a text/event-stream body into named events. */
export async function* readSse(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index !== -1) {
      const frame = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const eventLine = frame.split("\n").find((line) => line.startsWith("event: "));
      const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
      if (eventLine && dataLine) {
        yield {
          event: eventLine.slice(7).trim(),
          data: JSON.parse(dataLine.slice(6)) as Record<string, unknown>,
        };
      }
      index = buffer.indexOf("\n\n");
    }
  }
}
