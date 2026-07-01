"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

const LABELS: Record<string, string> = { uz: "UZ", ru: "RU" };

export function LocaleSwitcher() {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="flex items-center rounded-lg border border-zinc-800 p-0.5">
      {routing.locales.map((loc) => (
        <button
          key={loc}
          type="button"
          onClick={() => router.replace(pathname, { locale: loc })}
          aria-current={loc === locale ? "true" : undefined}
          className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
            loc === locale
              ? "bg-violet-600 text-white"
              : "text-zinc-400 hover:text-zinc-100"
          }`}
        >
          {LABELS[loc]}
        </button>
      ))}
    </div>
  );
}
