import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL, ACCESS_COOKIE } from "@/lib/config";

/**
 * Generic authenticated proxy for dashboard data calls (tenants, faqs,
 * channels, ...). The browser calls /api/proxy/tenants/me; this forwards to
 * FastAPI's /tenants/me with `Authorization: Bearer <access_token>` read
 * from the HttpOnly cookie. The browser never sees the JWT itself.
 *
 * Phase 6 only wires GET (for the topbar tenant name). Phase 7's FAQ /
 * channel CRUD screens will use POST/PATCH/DELETE through this same route —
 * left in now so that work doesn't need a second proxy layer.
 */
async function forward(
  request: NextRequest,
  path: string[],
  method: string
): Promise<NextResponse> {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const targetPath = `/${path.join("/")}`;
  const search = request.nextUrl.search;

  const hasBody = method === "POST" || method === "PATCH" || method === "PUT";
  let body: string | undefined;
  if (hasBody) {
    const text = await request.text();
    body = text || undefined;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}${targetPath}${search}`, {
      method,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the API server" },
      { status: 502 }
    );
  }

  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const text = await upstream.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  return NextResponse.json(data, { status: upstream.status });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return forward(request, (await params).path, "GET");
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return forward(request, (await params).path, "POST");
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return forward(request, (await params).path, "PATCH");
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return forward(request, (await params).path, "DELETE");
}
