import { NextRequest, NextResponse } from "next/server";
import { proxyToApi } from "@/lib/api/proxy";
import { REFRESH_COOKIE } from "@/lib/config";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    // Already logged out client-side; nothing to revoke.
    return NextResponse.json(null, { status: 204 });
  }

  return proxyToApi("/auth/logout", {
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}
