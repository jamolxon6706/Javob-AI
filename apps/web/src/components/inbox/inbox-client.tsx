"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";
import type {
  ConversationStatus,
  InboxConversationOut,
  InboxCopilotOut,
  InboxEvent,
  InboxMessageOut,
} from "@javobai/shared-types";
import { useInboxSocket } from "@/lib/ws/use-inbox-socket";

const PLATFORM_ICON: Record<string, string> = {
  telegram: "📱",
  whatsapp: "💬",
  instagram: "📷",
  facebook: "📘",
};

const STATUS_DOT: Record<ConversationStatus, string> = {
  waiting_operator: "bg-amber-500",
  open: "bg-emerald-500",
  bot_silenced: "bg-violet-500",
  resolved: "bg-zinc-500",
};

const MESSAGE_LIST_POLL_MS = 4000;
const CONVERSATION_LIST_POLL_MS = 6000;

function timeLabel(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

// ─── Conversation row ───────────────────────────────────────────────────────
function ConversationRow({
  conv,
  active,
  viewerNames,
  onSelect,
}: {
  conv: InboxConversationOut;
  active: boolean;
  viewerNames: string[];
  onSelect: () => void;
}) {
  const t = useTranslations("inbox");
  const contactLabel = conv.contact.name || `${t("unknownContact")} #${conv.contact.external_user_id}`;

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg border transition-colors ${
        active
          ? "border-violet-600 bg-violet-950/30"
          : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={`h-2 w-2 rounded-full shrink-0 ${STATUS_DOT[conv.status]}`} />
        <span className="text-sm font-medium text-zinc-100 truncate flex-1">
          {PLATFORM_ICON[conv.platform] ?? "💬"} {contactLabel}
        </span>
        {conv.last_message && (
          <span className="text-xs text-zinc-500 shrink-0">{timeLabel(conv.last_message.created_at)}</span>
        )}
      </div>
      <p className="text-xs text-zinc-500 truncate">
        {conv.last_message
          ? `${conv.last_message.direction === "outbound" ? "↩ " : ""}${conv.last_message.content ?? ""}`
          : t("noMessages")}
      </p>
      {viewerNames.length > 0 && (
        <p className="text-[11px] text-violet-400 mt-1 truncate">
          👀 {t("viewing", { names: viewerNames.join(", ") })}
        </p>
      )}
    </button>
  );
}

// ─── Message bubble ─────────────────────────────────────────────────────────
function MessageBubble({
  message,
  onAddToFaq,
}: {
  message: InboxMessageOut;
  onAddToFaq: (message: InboxMessageOut) => void;
}) {
  const t = useTranslations("inbox");
  const isOutbound = message.direction === "outbound";
  return (
    <div className={`group flex ${isOutbound ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] ${isOutbound ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap break-words ${
            isOutbound ? "bg-violet-600 text-white" : "bg-zinc-800 text-zinc-100"
          }`}
        >
          {message.content}
        </div>
        <div className="flex items-center gap-2 px-1">
          <span className="text-[11px] text-zinc-500">{timeLabel(message.created_at)}</span>
          {message.source && (
            <span className="text-[11px] text-zinc-600 uppercase">{message.source}</span>
          )}
          {isOutbound && message.content && (
            <button
              onClick={() => onAddToFaq(message)}
              className="text-[11px] text-zinc-600 opacity-0 group-hover:opacity-100 hover:text-violet-400 transition-opacity"
            >
              + {t("addToFaq.button")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Add-to-FAQ modal ───────────────────────────────────────────────────────
function AddToFaqModal({
  message,
  conversationId,
  onClose,
}: {
  message: InboxMessageOut;
  conversationId: string;
  onClose: () => void;
}) {
  const t = useTranslations("inbox");
  const tc = useTranslations("common");
  const [question, setQuestion] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!question.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/proxy/inbox/${conversationId}/messages/${message.id}/add-to-faq`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: question.trim() }),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? tc("error"));
      setSaved(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tc("error"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card className="w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-zinc-100">{t("addToFaq.modalTitle")}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 text-xl leading-none">
            ×
          </button>
        </div>
        {saved ? (
          <div className="space-y-4">
            <p className="text-sm text-emerald-400">✓ {t("addToFaq.saved")}</p>
            <Button onClick={onClose} className="w-full">
              {tc("close")}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("addToFaq.questionLabel")}
              </label>
              <Input
                placeholder={t("addToFaq.questionPlaceholder")}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("addToFaq.answerPreview")}
              </label>
              <p className="text-sm text-zinc-400 rounded-lg border border-zinc-800 bg-zinc-900/60 p-2.5 line-clamp-4">
                {message.content}
              </p>
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex gap-2 pt-1">
              <Button variant="secondary" onClick={onClose} className="flex-1" disabled={saving}>
                {tc("cancel")}
              </Button>
              <Button onClick={handleSave} className="flex-1" disabled={saving || !question.trim()}>
                {saving ? <Spinner size={14} /> : t("addToFaq.save")}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

// ─── Copilot panel ──────────────────────────────────────────────────────────
function CopilotPanel({
  conversationId,
  onUseSuggestion,
}: {
  conversationId: string;
  onUseSuggestion: (text: string) => void;
}) {
  const t = useTranslations("inbox");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<InboxCopilotOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setResult(null);
    setError(null);
  }, [conversationId]);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/proxy/inbox/${conversationId}/copilot`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(res.status === 503 ? t("copilot.notConfigured") : t("copilot.error"));
      }
      setResult(data as InboxCopilotOut);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("copilot.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-200">✨ {t("copilot.title")}</h3>
        <Button variant="secondary" onClick={handleGenerate} disabled={loading} className="text-xs">
          {loading ? <Spinner size={14} /> : t("copilot.generate")}
        </Button>
      </div>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      {result && (
        <div className="space-y-3">
          <div>
            <p className="text-[11px] uppercase text-zinc-500 mb-1">{t("copilot.summaryLabel")}</p>
            <p className="text-sm text-zinc-300">{result.summary}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase text-zinc-500 mb-1">{t("copilot.suggestionLabel")}</p>
            <p className="text-sm text-zinc-100 rounded-lg border border-zinc-800 bg-zinc-900/60 p-2.5">
              {result.suggestion}
            </p>
          </div>
          <Button onClick={() => onUseSuggestion(result.suggestion)} className="w-full text-xs">
            {t("copilot.useSuggestion")}
          </Button>
        </div>
      )}
    </Card>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────
export function InboxClient() {
  const t = useTranslations("inbox");

  const [conversations, setConversations] = useState<InboxConversationOut[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [statusFilter, setStatusFilter] = useState<"all" | ConversationStatus>("all");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<InboxMessageOut[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const [faqMessage, setFaqMessage] = useState<InboxMessageOut | null>(null);
  const [viewers, setViewers] = useState<Record<string, string[]>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);
  const selectedIdRef = useRef<string | null>(null);
  selectedIdRef.current = selectedId;

  const selected = useMemo(
    () => conversations.find((c) => c.id === selectedId) ?? null,
    [conversations, selectedId]
  );

  const patchConversation = useCallback(
    (id: string, patch: Partial<InboxConversationOut>) => {
      setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
    },
    []
  );

  const loadConversations = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoadingList(true);
    try {
      const params = statusFilter === "all" ? "" : `?status=${statusFilter}`;
      const res = await fetch(`/api/proxy/inbox${params}`);
      if (res.ok) setConversations(await res.json());
    } finally {
      if (showSpinner) setLoadingList(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const loadMessages = useCallback(async (conversationId: string, showSpinner = false) => {
    if (showSpinner) setLoadingMessages(true);
    try {
      const res = await fetch(`/api/proxy/inbox/${conversationId}/messages`);
      if (res.ok) setMessages(await res.json());
    } finally {
      if (showSpinner) setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    loadConversations(true);
  }, [loadConversations]);

  useEffect(() => {
    const id = setInterval(() => loadConversations(false), CONVERSATION_LIST_POLL_MS);
    return () => clearInterval(id);
  }, [loadConversations]);

  useEffect(() => {
    if (!selectedId) return;
    const id = setInterval(() => loadMessages(selectedId, false), MESSAGE_LIST_POLL_MS);
    return () => clearInterval(id);
  }, [selectedId, loadMessages]);

  useEffect(() => {
    if (messages.length > prevCountRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    prevCountRef.current = messages.length;
  }, [messages]);

  // ── Realtime ──────────────────────────────────────────────────────────────
  const { sendPresence } = useInboxSocket(
    useCallback(
      (event: InboxEvent) => {
        if (event.type === "handoff.created") {
          loadConversations(false);
        } else if (event.type === "message.created") {
          if (event.conversation_id === selectedIdRef.current) {
            setMessages((prev) =>
              prev.some((m) => m.id === event.message.id) ? prev : [...prev, event.message]
            );
          }
          loadConversations(false);
        } else if (event.type === "conversation.updated") {
          patchConversation(event.conversation_id, { status: event.status });
        } else if (event.type === "presence.update") {
          setViewers((prev) => ({ ...prev, [event.conversation_id]: event.viewers }));
        }
      },
      [loadConversations, patchConversation]
    )
  );

  function handleSelect(id: string) {
    if (selectedId) sendPresence(selectedId, false);
    setSelectedId(id);
    setReplyText("");
    setSendError(null);
    sendPresence(id, true);
    loadMessages(id, true);
  }

  async function handleSend() {
    if (!selected || !replyText.trim() || sending) return;
    setSending(true);
    setSendError(null);
    try {
      const res = await fetch(`/api/proxy/inbox/${selected.id}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: replyText.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? t("errors.replyFailed"));
      setMessages((prev) => [...prev, data as InboxMessageOut]);
      patchConversation(selected.id, { status: "open" });
      setReplyText("");
    } catch (e: unknown) {
      setSendError(e instanceof Error ? e.message : t("errors.replyFailed"));
    } finally {
      setSending(false);
    }
  }

  async function handleResolve() {
    if (!selected) return;
    const res = await fetch(`/api/proxy/inbox/${selected.id}/resolve`, { method: "POST" });
    if (res.ok) patchConversation(selected.id, { status: "resolved" });
  }

  async function handleAssign() {
    if (!selected) return;
    const res = await fetch(`/api/proxy/inbox/${selected.id}/assign`, { method: "POST" });
    if (res.ok) {
      const data = (await res.json()) as InboxConversationOut;
      patchConversation(selected.id, {
        status: data.status,
        assigned_operator_id: data.assigned_operator_id,
      });
    }
  }

  const filterOptions: Array<"all" | ConversationStatus> = [
    "all",
    "waiting_operator",
    "open",
    "resolved",
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr_280px] gap-4 h-[calc(100vh-200px)] min-h-[480px]">
      {/* Conversation list */}
      <Card className="flex flex-col overflow-hidden !p-3">
        <div className="flex gap-1 mb-3 overflow-x-auto pb-1">
          {filterOptions.map((opt) => (
            <button
              key={opt}
              onClick={() => setStatusFilter(opt)}
              className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                statusFilter === opt
                  ? "bg-violet-600 text-white"
                  : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
              }`}
            >
              {t(`filters.${opt}`)}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {loadingList ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-10 px-2">
              <p className="text-sm text-zinc-400">{t("noConversations")}</p>
              <p className="text-xs text-zinc-600 mt-1">{t("noConversationsHint")}</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <ConversationRow
                key={conv.id}
                conv={conv}
                active={conv.id === selectedId}
                viewerNames={viewers[conv.id] ?? []}
                onSelect={() => handleSelect(conv.id)}
              />
            ))
          )}
        </div>
      </Card>

      {/* Conversation view */}
      <Card className="flex flex-col overflow-hidden !p-0">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
            {t("selectConversation")}
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 border-b border-zinc-800 p-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-zinc-100 truncate">
                  {PLATFORM_ICON[selected.platform] ?? "💬"}{" "}
                  {selected.contact.name || `${t("unknownContact")} #${selected.contact.external_user_id}`}
                </p>
                <p className="text-xs text-zinc-500">{t(`status.${selected.status}`)}</p>
              </div>
              <div className="flex gap-2 shrink-0">
                {selected.status === "waiting_operator" && (
                  <Button variant="secondary" onClick={handleAssign} className="text-xs">
                    {t("assign")}
                  </Button>
                )}
                {selected.status !== "resolved" && (
                  <Button variant="secondary" onClick={handleResolve} className="text-xs">
                    {t("resolve")}
                  </Button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {loadingMessages ? (
                <div className="flex justify-center py-10">
                  <Spinner />
                </div>
              ) : messages.length === 0 ? (
                <p className="text-sm text-zinc-500 text-center py-10">{t("noMessages")}</p>
              ) : (
                messages.map((m) => (
                  <MessageBubble key={m.id} message={m} onAddToFaq={setFaqMessage} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-zinc-800 p-3 space-y-2">
              {sendError && <p className="text-xs text-red-400">{sendError}</p>}
              <div className="flex gap-2">
                <textarea
                  className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600 resize-none"
                  rows={2}
                  placeholder={t("composerPlaceholder")}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <Button onClick={handleSend} disabled={sending || !replyText.trim()} className="self-end">
                  {sending ? <Spinner size={14} /> : t("send")}
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* Copilot */}
      <div>
        {selected ? (
          <CopilotPanel conversationId={selected.id} onUseSuggestion={setReplyText} />
        ) : (
          <Card className="text-sm text-zinc-500">{t("selectConversation")}</Card>
        )}
      </div>

      {faqMessage && selected && (
        <AddToFaqModal
          message={faqMessage}
          conversationId={selected.id}
          onClose={() => setFaqMessage(null)}
        />
      )}
    </div>
  );
}
