import { NextRequest } from "next/server";
import { proxyToApi } from "@/lib/api/proxy";

export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyToApi("/auth/verify", { method: "POST", body });
}
