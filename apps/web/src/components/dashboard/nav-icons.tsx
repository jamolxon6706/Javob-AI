import type { SVGProps } from "react";
import type { NavItem } from "./nav-items";

type IconProps = SVGProps<SVGSVGElement>;

function Base({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={18}
      height={18}
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

const ICONS: Record<NavItem["icon"], (props: IconProps) => React.ReactElement> = {
  grid: (p) => (
    <Base {...p}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </Base>
  ),
  link: (p) => (
    <Base {...p}>
      <path d="M10 13a4 4 0 0 0 5.66 0l2-2a4 4 0 0 0-5.66-5.66l-1 1" />
      <path d="M14 11a4 4 0 0 0-5.66 0l-2 2a4 4 0 0 0 5.66 5.66l1-1" />
    </Base>
  ),
  book: (p) => (
    <Base {...p}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </Base>
  ),
  filter: (p) => (
    <Base {...p}>
      <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3Z" />
    </Base>
  ),
  inbox: (p) => (
    <Base {...p}>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z" />
    </Base>
  ),
  megaphone: (p) => (
    <Base {...p}>
      <path d="M3 11v3a1 1 0 0 0 1 1h2l3.5 5v-15L6 9H4a1 1 0 0 0-1 1Z" />
      <path d="M14 6a4 4 0 0 1 0 12" />
      <path d="M17 4a8 8 0 0 1 0 16" />
    </Base>
  ),
  chart: (p) => (
    <Base {...p}>
      <path d="M3 3v18h18" />
      <path d="M7 16l4-6 3 3 5-7" />
    </Base>
  ),
  sparkles: (p) => (
    <Base {...p}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
    </Base>
  ),
  "git-branch": (p) => (
    <Base {...p}>
      <line x1="6" y1="3" x2="6" y2="15" />
      <circle cx="18" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M18 9a9 9 0 0 1-9 9" />
    </Base>
  ),
  zap: (p) => (
    <Base {...p}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </Base>
  ),
  card: (p) => (
    <Base {...p}>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20" />
    </Base>
  ),
};

export function NavIcon({ name, ...props }: { name: NavItem["icon"] } & IconProps) {
  const Icon = ICONS[name];
  return <Icon {...props} />;
}
