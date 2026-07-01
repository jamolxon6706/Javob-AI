import { cookies } from "next/headers";
import type { MeOut, TenantOut } from "@javobai/shared-types";
import { API_BASE_URL, ACCESS_COOKIE } from "@/lib/config";
import { decodeAccessToken, isExpired } from "@/lib/auth/jwt";

/**
 * Fetch helpers for use inside React Server Components / layouts. These run
 * on the server already, so they call FastAPI directly (no need to hop
 * through our own /api/proxy route) — they just need the access token off
 * the incoming request's cookie jar.
 */
async function authedFetch<T>(path: string): Promise<T | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) return null;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as T;
}

export async function getCurrentTenant(): Promise<TenantOut | null> {
  return authedFetch<TenantOut>("/tenants/me");
}

export async function getCurrentUser(): Promise<MeOut | null> {
  return authedFetch<MeOut>("/auth/me");
}

/** True if the access cookie is present and not expired (no network call). */
export async function hasValidAccessToken(): Promise<boolean> {
  const cookieStore = await cookies();
  const token = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!token) return false;
  const payload = decodeAccessToken(token);
  return payload !== null && !isExpired(payload);
}
