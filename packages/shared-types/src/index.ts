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
