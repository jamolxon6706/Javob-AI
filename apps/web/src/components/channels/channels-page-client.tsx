"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";

interface Channel {
  id: string;
  platform: string;
  bot_username: string | null;
  is_active: boolean;
  webhook_url: string;
}

interface TelegramModalProps {
  onClose: () => void;
  onSuccess: (channel: Channel) => void;
}

function TelegramModal({ onClose, onSuccess }: TelegramModalProps) {
  const t = useTranslations("channels");
  const tc = useTranslations("common");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Channel | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleConnect() {
    if (!token.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/channels/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: token.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? tc("error"));
      setResult(data as Channel);
      onSuccess(data as Channel);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tc("error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <Card className="w-full max-w-md mx-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-zinc-100">
            {t("telegramModal.title")}
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 transition-colors text-xl leading-none"
          >
            ×
          </button>
        </div>

        {result ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-green-400">
              <span className="text-xl">✓</span>
              <span className="font-medium">{t("telegramModal.success")}</span>
            </div>
            {result.bot_username && (
              <p className="text-zinc-300 text-sm">
                {t("telegramModal.botUsername", { username: result.bot_username })}
              </p>
            )}
            <p className="text-zinc-500 text-xs break-all">
              {t("telegramModal.webhookUrl", { url: result.webhook_url })}
            </p>
            <Button onClick={onClose} className="w-full mt-2">
              {tc("close")}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("telegramModal.tokenLabel")}
              </label>
              <Input
                placeholder={t("telegramModal.tokenPlaceholder")}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                error={error ?? undefined}
              />
              <p className="mt-1.5 text-xs text-zinc-500">
                {t("telegramModal.tokenHint")}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={onClose}
                className="flex-1"
                disabled={loading}
              >
                {tc("cancel")}
              </Button>
              <Button
                onClick={handleConnect}
                className="flex-1"
                disabled={loading || !token.trim()}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <Spinner size={14} />
                    {t("telegramModal.connecting")}
                  </span>
                ) : (
                  t("telegramModal.connect")
                )}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

const PLATFORM_ICONS: Record<string, string> = {
  telegram: "✈️",
  whatsapp: "💬",
  instagram: "📷",
  facebook: "👤",
};

function ChannelCard({ channel }: { channel: Channel }) {
  const t = useTranslations("channels");
  const icon = PLATFORM_ICONS[channel.platform] ?? "🔌";
  const platformLabel =
    t(`platform.${channel.platform}` as Parameters<typeof t>[0]) ??
    channel.platform;

  return (
    <Card className="flex items-center gap-4">
      <div className="text-2xl w-10 h-10 flex items-center justify-center rounded-lg bg-zinc-800">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-zinc-100">{platformLabel}</span>
          {channel.bot_username && (
            <span className="text-xs text-zinc-500">@{channel.bot_username}</span>
          )}
        </div>
        <p className="text-xs text-zinc-500 truncate mt-0.5">{channel.webhook_url}</p>
      </div>
      <span
        className={`shrink-0 text-xs px-2.5 py-1 rounded-full font-medium ${
          channel.is_active
            ? "bg-green-900/40 text-green-400"
            : "bg-zinc-800 text-zinc-500"
        }`}
      >
        {channel.is_active ? t("status.active") : t("status.inactive")}
      </span>
    </Card>
  );
}

export function ChannelsPageClient() {
  const t = useTranslations("channels");
  const tc = useTranslations("common");
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTelegramModal, setShowTelegramModal] = useState(false);

  const loadChannels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/channels");
      if (res.ok) setChannels(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  function handleConnected(ch: Channel) {
    setChannels((prev) => {
      const idx = prev.findIndex((c) => c.id === ch.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = ch;
        return next;
      }
      return [ch, ...prev];
    });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div />
        <div className="flex gap-2">
          <Button onClick={() => setShowTelegramModal(true)}>
            ✈️ {t("connectTelegram")}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : channels.length === 0 ? (
        <Card className="flex flex-col items-center justify-center py-16 text-center">
          <div className="text-4xl mb-3">📡</div>
          <p className="text-zinc-300 font-medium">{t("noChannels")}</p>
          <p className="text-zinc-500 text-sm mt-1">{t("noChannelsHint")}</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {channels.map((ch) => (
            <ChannelCard key={ch.id} channel={ch} />
          ))}
        </div>
      )}

      {showTelegramModal && (
        <TelegramModal
          onClose={() => setShowTelegramModal(false)}
          onSuccess={(ch) => {
            handleConnected(ch);
          }}
        />
      )}
    </div>
  );
}
