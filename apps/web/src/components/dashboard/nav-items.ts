export interface NavItem {
  /** matches a key under messages.nav.* */
  labelKey:
    | "dashboard"
    | "channels"
    | "knowledgeBase"
    | "rules"
    | "inbox"
    | "campaigns"
    | "analytics"
    | "aiSettings"
    | "billing"
    | "flows"
    | "actions";
  href: string;
  icon: "grid" | "link" | "book" | "filter" | "inbox" | "megaphone" | "chart" | "sparkles" | "card" | "git-branch" | "zap";
}

export const NAV_ITEMS: NavItem[] = [
  { labelKey: "dashboard", href: "/dashboard", icon: "grid" },
  { labelKey: "channels", href: "/channels", icon: "link" },
  { labelKey: "knowledgeBase", href: "/knowledge-base", icon: "book" },
  { labelKey: "rules", href: "/rules", icon: "filter" },
  { labelKey: "inbox", href: "/inbox", icon: "inbox" },
  { labelKey: "flows", href: "/flows", icon: "git-branch" },
  { labelKey: "actions", href: "/actions", icon: "zap" },
  { labelKey: "campaigns", href: "/campaigns", icon: "megaphone" },
  { labelKey: "analytics", href: "/analytics", icon: "chart" },
  { labelKey: "aiSettings", href: "/ai-settings", icon: "sparkles" },
  { labelKey: "billing", href: "/billing", icon: "card" },
];
