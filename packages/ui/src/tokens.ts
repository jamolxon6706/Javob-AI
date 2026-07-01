/**
 * Shared design tokens for the JavobAI dashboard (dark theme).
 *
 * These are plain values (not CSS vars) so both Tailwind utility classes and
 * the future landing page (Phase 15) can reference the same palette without
 * importing Tailwind config across the workspace boundary.
 */
export const tokens = {
  color: {
    bg: "#09090b", // zinc-950
    surface: "#18181b", // zinc-900
    border: "#27272a", // zinc-800
    textPrimary: "#fafafa", // zinc-50
    textMuted: "#a1a1aa", // zinc-400
    accent: "#7c3aed", // violet-600
    accentHover: "#6d28d9", // violet-700
    danger: "#ef4444", // red-500
    success: "#22c55e", // green-500
  },
  radius: {
    sm: "0.375rem",
    md: "0.5rem",
    lg: "0.75rem",
  },
} as const;
