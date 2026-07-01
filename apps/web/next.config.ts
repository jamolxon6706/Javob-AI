import type { NextConfig } from "next";

/**
 * Manually wiring next-intl's Turbopack alias instead of using
 * `createNextIntlPlugin()` from next-intl@3.26: that plugin injects
 * `experimental.turbo.resolveAlias`, the pre-Next.js-16 config shape.
 * Next.js 16 moved Turbopack config to a top-level `turbopack` key and
 * dropped `experimental.turbo`, so the plugin's alias silently never
 * applies and next-intl can't find its request config at runtime
 * ("Couldn't find next-intl config file"). Setting the alias directly
 * under `turbopack.resolveAlias` is the Next 16-native equivalent.
 */
const nextConfig: NextConfig = {
  turbopack: {
    resolveAlias: {
      "next-intl/config": "./src/i18n/request.ts",
    },
  },
};

export default nextConfig;
