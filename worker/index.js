const API_PREFIX = "/api/";

function upstreamConfiguration(env) {
  const secret = env.FORTUNE_PROXY_SECRET;
  let origin;
  try {
    origin = new URL(env.FORTUNE_API_ORIGIN);
  } catch {
    return null;
  }
  if (
    origin.protocol !== "https:" ||
    !origin.hostname.endsWith(".onrender.com") ||
    origin.pathname !== "/" ||
    origin.search ||
    origin.hash ||
    typeof secret !== "string" ||
    secret.length < 32
  ) {
    return null;
  }
  return { origin, secret };
}

async function proxyApi(request, env) {
  const incoming = new URL(request.url);
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
    const browserOrigin = request.headers.get("origin");
    if (browserOrigin && browserOrigin !== incoming.origin) {
      return Response.json({ error: "Request origin is not allowed" }, { status: 403 });
    }
  }
  const configuration = upstreamConfiguration(env);
  if (!configuration) {
    return Response.json({ error: "API hosting is not configured" }, { status: 503 });
  }
  const upstream = new URL(incoming.pathname + incoming.search, configuration.origin);
  const headers = new Headers(request.headers);
  for (const name of [
    "cookie",
    "host",
    "origin",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-fortune-proxy-secret",
  ]) {
    headers.delete(name);
  }
  headers.set("X-Fortune-Proxy-Secret", configuration.secret);
  let response;
  try {
    response = await fetch(new Request(upstream, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      duplex: "half",
      redirect: "manual",
    }));
  } catch {
    return Response.json({ error: "API hosting is temporarily unavailable" }, { status: 502 });
  }
  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("set-cookie");
  responseHeaders.set("cache-control", "no-store");
  const location = responseHeaders.get("location");
  if (location) {
    const redirect = new URL(location, configuration.origin);
    if (redirect.origin !== configuration.origin.origin) {
      return Response.json({ error: "Unexpected API redirect" }, { status: 502 });
    }
    redirect.protocol = incoming.protocol;
    redirect.host = incoming.host;
    responseHeaders.set("location", redirect.href);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith(API_PREFIX)) {
      return proxyApi(request, env);
    }
    const response = await env.ASSETS.fetch(request);
    const acceptsHtml = request.headers.get("accept")?.includes("text/html");
    if (response.status !== 404 || !acceptsHtml || !["GET", "HEAD"].includes(request.method)) {
      return response;
    }
    const indexUrl = new URL(request.url);
    indexUrl.pathname = "/index.html";
    indexUrl.search = "";
    return env.ASSETS.fetch(new Request(indexUrl, request));
  },
};
