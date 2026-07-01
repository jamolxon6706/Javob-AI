"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "@/i18n/navigation";

/**
 * Renders nothing. On mount, if `shouldRefresh` is true (the access token
 * was missing/expired but a refresh token cookie exists — decided server-
 * side in the dashboard layout), silently calls POST /api/auth/refresh and
 * then triggers a router.refresh() so server components re-render with the
 * new access cookie attached to the next request.
 */
export function AuthRefresher({ shouldRefresh }: { shouldRefresh: boolean }) {
  const router = useRouter();
  const ranOnce = useRef(false);

  useEffect(() => {
    if (!shouldRefresh || ranOnce.current) return;
    ranOnce.current = true;

    fetch("/api/auth/refresh", { method: "POST" })
      .then((res) => {
        if (res.ok) {
          router.refresh();
        } else {
          router.replace("/login");
        }
      })
      .catch(() => router.replace("/login"));
  }, [shouldRefresh, router]);

  return null;
}
