import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/config";

/**
 * Proxy a JSON request to the FastAPI backend and relay any Set-Cookie
 * headers it returns. fetch() in Node strips/merges Set-Cookie when there
 * are multiple (access + refresh), so we read the raw headers via
 * `headers.getSetCookie()` (undici/Node 20+) and re-attach each one
 * individually on the NextResponse.
 */
export async function proxyToApi(
  path: string,
  init: { method: string; body?: unknown; cookieHeader?: string }
): Promise<NextResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init.cookieHeader) {
    headers["Cookie"] = init.cookieHeader;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method,
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the API server" },
      { status: 502 }
    );
  }

  let data: unknown = null;
  const text = await upstream.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  const response = NextResponse.json(data, { status: upstream.status });

  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [];
  for (const cookie of setCookies) {
    response.headers.append("Set-Cookie", cookie);
  }

  return response;
}
