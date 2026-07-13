import { describe, expect, it } from "vitest";

import app from "./app";

describe("GET /health", () => {
  it("returns 200 with status ok and an ISO timestamp", async () => {
    const res = await app.request("/health");

    expect(res.status).toBe(200);
    const body = (await res.json()) as { status: string; timestamp: string };
    expect(body.status).toBe("ok");
    // timestamp must round-trip as a valid ISO-8601 instant
    expect(new Date(body.timestamp).toISOString()).toBe(body.timestamp);
  });

  it("serves CORS headers for cross-origin callers", async () => {
    const res = await app.request("/health", {
      headers: { Origin: "http://localhost:3000" },
    });

    expect(res.headers.get("access-control-allow-origin")).toBe("*");
  });

  it("404s unknown routes", async () => {
    const res = await app.request("/nope");

    expect(res.status).toBe(404);
  });
});
