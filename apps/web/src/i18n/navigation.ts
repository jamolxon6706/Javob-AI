import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

/**
 * Locale-aware drop-in replacements for next/link, next/navigation.
 * Use these everywhere instead of the raw Next.js equivalents so links and
 * redirects automatically carry the current locale prefix.
 */
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
