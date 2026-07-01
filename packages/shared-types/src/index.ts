/** Platform enum matching the backend Platform model */
export type Platform = "telegram" | "whatsapp" | "instagram" | "facebook";

/** Kind of message/event */
export type MessageKind = "dm" | "comment" | "comment_reply";

/** Normalized message contract shared between all platform adapters */
export interface UnifiedMessage {
  tenant_id: string;
  platform: Platform;
  channel_id: string;
  kind: MessageKind;
  external_user_id: string;
  conversation_id: string;
  text: string;
  media: MediaItem[];
  lang_hint: string | null;
  raw: Record<string, unknown>;
  received_at: string; // ISO-8601
}

export interface MediaItem {
  type: "image" | "video" | "audio" | "document";
  url: string;
  mime_type: string | null;
}

export interface ApiHealthResponse {
  status: "ok";
}

// ── Auth (matches apps/api/src/javobai/auth/router.py) ──────────────────────

export interface RequestOtpIn {
  phone: string;
}

export interface RequestOtpOut {
  detail: string;
  otp?: string | null; // only populated outside production
}

export interface VerifyOtpIn {
  phone: string;
  otp: string;
}

export interface TokenOut {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export type UserRole = "owner" | "admin" | "operator";

export interface MeOut {
  id: string;
  tenant_id: string;
  phone: string;
  name: string | null;
  role: UserRole;
}

// ── Tenants (matches apps/api/src/javobai/tenants/router.py) ────────────────

export type TenantPlan = "free" | "pro" | "business";

export interface TenantOut {
  id: string;
  name: string;
  slug: string;
  plan: TenantPlan;
  is_active: boolean;
}

export interface TenantUpdateIn {
  name?: string;
  settings?: Record<string, unknown>;
}

// ── FAQs (matches apps/api/src/javobai/faqs/router.py) ───────────────────────

export type FaqLanguage = "uz" | "ru";

export interface FaqOut {
  id: string;
  tenant_id: string;
  question: string;
  answer: string;
  category: string | null;
  language: FaqLanguage;
  is_active: boolean;
}

export interface FaqIn {
  question: string;
  answer: string;
  category?: string | null;
  language?: FaqLanguage;
}

export interface FaqUpdateIn {
  question?: string;
  answer?: string;
  category?: string | null;
  language?: FaqLanguage;
  is_active?: boolean;
}

// ── Channels (matches apps/api/src/javobai/channels/router.py) ─────────────

export interface TelegramOnboardIn {
  bot_token: string;
}

export interface ChannelOut {
  id: string;
  platform: Platform;
  bot_username: string | null;
  is_active: boolean;
  webhook_url: string;
}

// ── Generic API error envelope (FastAPI HTTPException default shape) ───────

export interface ApiErrorOut {
  detail: string;
}

// ── Inbox (matches apps/api/src/javobai/inbox/router.py) ───────────────────

/** open | waiting_operator | resolved | bot_silenced */
export type ConversationStatus = "open" | "waiting_operator" | "resolved" | "bot_silenced";

/** inbound | outbound */
export type MessageDirection = "inbound" | "outbound";

/** rule | faq | llm | action | operator */
export type MessageSource = "rule" | "faq" | "llm" | "action" | "operator" | null;

export interface InboxContactOut {
  id: string;
  platform: Platform;
  external_user_id: string;
  name: string | null;
  phone: string | null;
}

export interface InboxLastMessageOut {
  content: string | null;
  direction: MessageDirection;
  source: MessageSource;
  created_at: string; // ISO-8601
}

export interface InboxConversationOut {
  id: string;
  channel_id: string;
  platform: Platform;
  status: ConversationStatus;
  contact: InboxContactOut;
  last_message: InboxLastMessageOut | null;
  assigned_operator_id: string | null;
  bot_silenced_until: string | null;
  window_expires_at: string | null;
  updated_at: string;
}

export interface InboxMessageOut {
  id: string;
  conversation_id: string;
  direction: MessageDirection;
  content: string | null;
  source: MessageSource;
  rag_score: number | null;
  created_at: string;
}

export interface InboxReplyIn {
  text: string;
}

export interface InboxCopilotOut {
  summary: string;
  suggestion: string;
}

export interface InboxAddToFaqIn {
  question: string;
  answer?: string | null;
}

export interface InboxAddToFaqOut {
  id: string;
  question: string;
  answer: string;
}

// ── Realtime (matches apps/api/src/javobai/ws/router.py) ───────────────────

export interface WsTicketOut {
  ticket: string;
}

export type InboxEvent =
  | { type: "handoff.created"; conversation_id: string; reason: string; rag_score: number | null }
  | { type: "message.created"; conversation_id: string; message: InboxMessageOut }
  | { type: "conversation.updated"; conversation_id: string; status: ConversationStatus }
  | { type: "presence.update"; conversation_id: string; viewers: string[] };
