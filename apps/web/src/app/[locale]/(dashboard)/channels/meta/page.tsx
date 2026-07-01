"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";

type Platform = "instagram" | "facebook";

interface ConnectResult {
  page_id: string;
  page_name: string;
  status: string;
}

interface PermissionError {
  error: string;
  missing: string[];
  help: string;
}

const PLATFORM_META: Record<
  Platform,
  { label: string; icon: string; color: string; permissions: string[] }
> = {
  instagram: {
    label: "Instagram",
    icon: "📸",
    color: "from-pink-500 to-orange-400",
    permissions: [
      "instagram_basic",
      "instagram_manage_messages",
      "instagram_manage_comments",
      "pages_read_engagement",
    ],
  },
  facebook: {
    label: "Facebook",
    icon: "💬",
    color: "from-blue-600 to-blue-400",
    permissions: [
      "pages_messaging",
      "pages_read_engagement",
      "pages_manage_metadata",
    ],
  },
};

export default function MetaChannelConnectPage() {
  const t = useTranslations("channels.meta");
  const [platform, setPlatform] = useState<Platform>("instagram");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ConnectResult | null>(null);
  const [permError, setPermError] = useState<PermissionError | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = async () => {
    setLoading(true);
    setResult(null);
    setPermError(null);
    setError(null);

    try {
      const r = await apiClient.post("/channels/meta/connect", {
        platform,
        access_token: token,
      });
      setResult(r.data);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: PermissionError | string } } };
      const detail = err?.response?.data?.detail;
      if (
        detail &&
        typeof detail === "object" &&
        "missing" in detail
      ) {
        setPermError(detail as PermissionError);
      } else {
        setError(
          typeof detail === "string"
            ? detail
            : "Ulanishda xato yuz berdi. Token yoki ruxsatlarni tekshiring."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const meta = PLATFORM_META[platform];

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold mb-1">{t("title")}</h1>
      <p className="text-muted-foreground text-sm mb-8">{t("subtitle")}</p>

      {/* Platform selector */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        {(["instagram", "facebook"] as Platform[]).map((p) => {
          const m = PLATFORM_META[p];
          return (
            <button
              key={p}
              onClick={() => {
                setPlatform(p);
                setResult(null);
                setPermError(null);
                setError(null);
              }}
              className={`flex items-center gap-3 rounded-xl p-4 border-2 transition ${
                platform === p
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/40"
              }`}
            >
              <span className="text-2xl">{m.icon}</span>
              <div className="text-left">
                <p className="font-medium text-sm">{m.label}</p>
                <p className="text-xs text-muted-foreground">
                  {t(`${p}_desc`)}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Steps */}
      <div className="bg-muted/40 rounded-xl p-5 mb-6 space-y-3">
        <p className="text-sm font-semibold">{t("how_to")}</p>
        <ol className="text-sm text-muted-foreground space-y-2 list-decimal list-inside leading-relaxed">
          <li>
            {t("step1")}{" "}
            <a
              href="https://developers.facebook.com/apps"
              target="_blank"
              rel="noreferrer"
              className="text-primary underline"
            >
              Meta for Developers
            </a>
          </li>
          <li>{t("step2")}</li>
          <li>
            {t("step3")}:
            <div className="mt-1 ml-4 flex flex-wrap gap-1">
              {meta.permissions.map((p) => (
                <code
                  key={p}
                  className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono"
                >
                  {p}
                </code>
              ))}
            </div>
          </li>
          <li>{t("step4")}</li>
        </ol>
      </div>

      {/* Token input */}
      <div className="space-y-2 mb-4">
        <label className="text-sm font-medium">
          {t("token_label")} ({meta.label})
        </label>
        <textarea
          rows={3}
          value={token}
          onChange={(e) => setToken(e.target.value.trim())}
          placeholder="EAA..."
          className="w-full text-sm bg-muted rounded-xl px-3 py-2.5 outline-none resize-none font-mono"
        />
      </div>

      <button
        onClick={connect}
        disabled={loading || !token}
        className="w-full bg-primary text-primary-foreground rounded-xl py-2.5 text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition"
      >
        {loading ? t("connecting") : t("connect")}
      </button>

      {/* Success */}
      {result && (
        <div className="mt-5 border border-green-500/30 bg-green-500/5 rounded-xl p-4">
          <p className="text-green-500 font-semibold text-sm">
            ✓ {t("connected")}
          </p>
          <p className="text-sm mt-1">
            <span className="text-muted-foreground">{t("page_name")}: </span>
            <span className="font-medium">{result.page_name}</span>
          </p>
          <p className="text-sm">
            <span className="text-muted-foreground">Page ID: </span>
            <code className="font-mono text-xs">{result.page_id}</code>
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            {t("webhook_note")}:{" "}
            <code className="font-mono">
              https://yourdomain.com/webhooks/{platform}
            </code>
          </p>
        </div>
      )}

      {/* Permission error */}
      {permError && (
        <div className="mt-5 border border-orange-500/30 bg-orange-500/5 rounded-xl p-4 space-y-2">
          <p className="text-orange-500 font-semibold text-sm">
            ⚠ {t("permission_error")}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("missing_permissions")}:
          </p>
          <div className="flex flex-wrap gap-1">
            {permError.missing.map((p) => (
              <code
                key={p}
                className="text-xs bg-orange-500/10 text-orange-500 px-1.5 py-0.5 rounded font-mono"
              >
                {p}
              </code>
            ))}
          </div>
          <a
            href="https://developers.facebook.com/apps"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-primary underline block mt-1"
          >
            {t("app_review_link")} →
          </a>
        </div>
      )}

      {/* Generic error */}
      {error && (
        <div className="mt-5 border border-destructive/30 bg-destructive/5 rounded-xl p-4">
          <p className="text-destructive text-sm">{error}</p>
        </div>
      )}
    </div>
  );
}
