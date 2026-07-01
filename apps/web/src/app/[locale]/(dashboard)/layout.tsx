import type { ReactNode } from "react";
import { Sidebar } from "@/components/dashboard/sidebar";
import { Topbar } from "@/components/dashboard/topbar";
import { AuthRefresher } from "@/components/dashboard/auth-refresher";
import {
  getCurrentTenant,
  getCurrentUser,
  hasValidAccessToken,
} from "@/lib/api/server";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Middleware already guarantees a session (valid access OR refresh
  // cookie) exists before this layout renders. If the access token itself
  // has expired, fetch with it will fail — so we ask AuthRefresher to do a
  // silent refresh, and skip the data fetch this pass (it'll re-run after
  // router.refresh()).
  const validAccess = await hasValidAccessToken();

  const [tenant, user] = validAccess
    ? await Promise.all([getCurrentTenant(), getCurrentUser()])
    : [null, null];

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950">
      <AuthRefresher shouldRefresh={!validAccess} />
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar tenant={tenant} user={user} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
