import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import worker from "./index.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

const env = {
  FORTUNE_API_ORIGIN: "https://fortune-copilot-v6-api.onrender.com",
  FORTUNE_PROXY_SECRET: "test-secret-for-hosted-proxy-at-least-32-characters",
  ASSETS: { fetch: async () => new Response("asset", { status: 200 }) },
};

test("API proxy is unavailable until both runtime values are configured", async () => {
  const response = await worker.fetch(new Request("https://site.example/api/v1/health"), {
    ...env,
    FORTUNE_PROXY_SECRET: undefined,
  });
  assert.equal(response.status, 503);
});

test("API proxy injects the secret and removes spoofed client headers", async () => {
  let forwarded;
  globalThis.fetch = async (request) => {
    forwarded = request;
    return Response.json({ status: "ok" });
  };
  const response = await worker.fetch(new Request("https://site.example/api/v1/health?x=1", {
    headers: {
      Origin: "https://evil.example",
      Cookie: "private=value",
      "X-Fortune-Proxy-Secret": "attacker-value",
    },
  }), env);
  assert.equal(response.status, 200);
  assert.equal(forwarded.url, "https://fortune-copilot-v6-api.onrender.com/api/v1/health?x=1");
  assert.equal(forwarded.headers.get("X-Fortune-Proxy-Secret"), env.FORTUNE_PROXY_SECRET);
  assert.equal(forwarded.headers.get("Origin"), null);
  assert.equal(forwarded.headers.get("Cookie"), null);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("non-API routes continue to use static assets", async () => {
  const response = await worker.fetch(new Request("https://site.example/", {
    headers: { Accept: "text/html" },
  }), env);
  assert.equal(await response.text(), "asset");
});

test("POST body reaches the upstream without browser origin headers", async () => {
  let forwarded;
  globalThis.fetch = async (request) => {
    forwarded = request;
    return Response.json({ saved: true });
  };
  const response = await worker.fetch(new Request("https://site.example/api/v1/households", {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: "https://site.example" },
    body: JSON.stringify({ synthetic: true }),
  }), env);
  assert.equal(response.status, 200);
  assert.deepEqual(await forwarded.json(), { synthetic: true });
  assert.equal(forwarded.headers.get("origin"), null);
});

test("upstream redirects stay on the Sites origin", async () => {
  globalThis.fetch = async () => new Response(null, {
    status: 307,
    headers: { Location: "https://fortune-copilot-v6-api.onrender.com/api/v1/households/" },
  });
  const response = await worker.fetch(new Request("https://site.example/api/v1/households"), env);
  assert.equal(response.headers.get("location"), "https://site.example/api/v1/households/");
});

test("cross-origin writes are rejected before reaching the backend", async () => {
  const response = await worker.fetch(new Request("https://site.example/api/v1/households", {
    method: "POST",
    headers: { Origin: "https://evil.example" },
    body: "{}",
  }), env);
  assert.equal(response.status, 403);
});
