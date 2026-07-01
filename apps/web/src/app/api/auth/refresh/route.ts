import { NextRequest, NextResponse } from "next/server";
import { proxyToApi } from "@/lib/api/proxy";
import { REFRESH_COOKIE } from "@/lib/config";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json({ detail: "No refresh token" }, { status: 401 });
  }

  return proxyToApi("/auth/refresh", {
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}
