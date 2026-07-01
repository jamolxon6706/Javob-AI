import { defineRouting } from "next-intl/routing";

/**
 * Supported locales for the dashboard + landing.
 * `uz` (Latin script) is the default — most JavobAI tenants and their
 * customers operate in Uzbek; `ru` is the secondary market language.
 */
export const routing = defineRouting({
  locales: ["uz", "ru"],
  defaultLocale: "uz",
  // "as-needed": default locale (uz) has no URL prefix → /login, /dashboard
  // secondary locale is prefixed → /ru/login, /ru/dashboard
  localePrefix: "as-needed",
});

export type AppLocale = (typeof routing.locales)[number];

/**
 * Type-guard equivalent of next-intl v4's `hasLocale()` helper, which isn't
 * exported by the v3.26 release pinned in this project. Narrows an unknown
 * string to AppLocale if it's one of our configured locales.
 */
export function hasLocale(
  locales: readonly string[],
  candidate: string | undefined
): candidate is AppLocale {
  return candidate !== undefined && locales.includes(candidate);
}
