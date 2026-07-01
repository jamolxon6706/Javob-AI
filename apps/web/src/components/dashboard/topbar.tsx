"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Button } from "@javobai/ui";
import { logout } from "@/lib/api/auth";
import type { MeOut, TenantOut } from "@javobai/shared-types";
import { LocaleSwitcher } from "./locale-switcher";

interface TopbarProps {
  tenant: TenantOut | null;
  user: MeOut | null;
}

export function Topbar({ tenant, user }: TopbarProps) {
  const t = useTranslations("topbar");
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  function handleLogout() {
    startTransition(async () => {
      await logout();
      router.replace("/login");
      router.refresh();
    });
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-5">
      <div className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-zinc-200 hover:bg-zinc-900"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-zinc-800 text-xs font-semibold uppercase text-zinc-300">
            {tenant?.name?.charAt(0) ?? "?"}
          </span>
          <span className="font-medium">{tenant?.name ?? "—"}</span>
          {tenant ? (
            <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[11px] uppercase tracking-wide text-zinc-400">
              {tenant.plan}
            </span>
          ) : null}
        </button>

        {menuOpen ? (
          <div className="absolute left-0 top-full z-10 mt-1 w-56 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl">
            <p className="px-3 py-2 text-xs text-zinc-500">{t("switchTenant")}</p>
            <button
              type="button"
              disabled
              className="w-full rounded-md px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
            >
              {tenant?.name ?? "—"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <LocaleSwitcher />
        {user ? (
          <span className="hidden text-sm text-zinc-400 sm:inline">{user.phone}</span>
        ) : null}
        <Button variant="ghost" onClick={handleLogout} disabled={pending}>
          {t("logout")}
        </Button>
      </div>
    </header>
  );
}
