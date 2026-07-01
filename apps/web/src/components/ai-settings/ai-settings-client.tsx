"use client";

import { useState, useEffect, KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";

interface AISettings {
  brand_voice: string;
  confidence_threshold: number;
  llm_enabled: boolean;
  banned_topics: string[];
  language_mode: string;
}

export function AISettingsClient() {
  const t = useTranslations("aiSettings");
  const tc = useTranslations("common");
  const [settings, setSettings] = useState<AISettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [topicInput, setTopicInput] = useState("");

  useEffect(() => {
    fetch("/api/proxy/ai-settings")
      .then((r) => r.json())
      .then((data) => setSettings(data as AISettings))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    try {
      const res = await fetch("/api/proxy/ai-settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data as AISettings);
        setSaved(true);
        setTimeout(() => setSaved(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  }

  function addTopic() {
    const topic = topicInput.trim();
    if (!topic || !settings) return;
    if (!settings.banned_topics.includes(topic)) {
      setSettings({ ...settings, banned_topics: [...settings.banned_topics, topic] });
    }
    setTopicInput("");
  }

  function removeTopic(topic: string) {
    if (!settings) return;
    setSettings({
      ...settings,
      banned_topics: settings.banned_topics.filter((t) => t !== topic),
    });
  }

  function handleTopicKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addTopic();
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (!settings) return null;

  const confidencePct = Math.round(settings.confidence_threshold * 100);

  return (
    <div className="max-w-2xl space-y-5">
      {/* Brand Voice */}
      <Card>
        <h3 className="text-sm font-semibold text-zinc-200 mb-1">
          🎙️ {t("brandVoiceLabel")}
        </h3>
        <p className="text-xs text-zinc-500 mb-3">{t("brandVoiceHint")}</p>
        <textarea
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600 resize-none"
          rows={4}
          placeholder={t("brandVoicePlaceholder")}
          value={settings.brand_voice}
          onChange={(e) =>
            setSettings({ ...settings, brand_voice: e.target.value })
          }
        />
      </Card>

      {/* LLM Toggle + Confidence */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">{t("llmLabel")}</h3>
            <p className="text-xs text-zinc-500 mt-0.5">{t("llmHint")}</p>
          </div>
          <div
            onClick={() =>
              setSettings({ ...settings, llm_enabled: !settings.llm_enabled })
            }
            className={`relative w-12 h-6 rounded-full transition-colors cursor-pointer ${
              settings.llm_enabled ? "bg-violet-600" : "bg-zinc-700"
            }`}
          >
            <div
              className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                settings.llm_enabled ? "translate-x-7" : "translate-x-1"
              }`}
            />
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span
            className={`px-2 py-1 rounded-full ${
              !settings.llm_enabled
                ? "bg-violet-900/40 text-violet-400"
                : "bg-zinc-800"
            }`}
          >
            {t("faqOnlyMode")}
          </span>
          <span>→</span>
          <span
            className={`px-2 py-1 rounded-full ${
              settings.llm_enabled
                ? "bg-violet-900/40 text-violet-400"
                : "bg-zinc-800"
            }`}
          >
            {t("llmMode")}
          </span>
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-zinc-200">
              {t("confidenceLabel")}
            </h3>
            <span className="text-sm font-mono text-violet-400">
              {confidencePct}%
            </span>
          </div>
          <input
            type="range"
            min={40}
            max={95}
            step={5}
            value={confidencePct}
            onChange={(e) =>
              setSettings({
                ...settings,
                confidence_threshold: Number(e.target.value) / 100,
              })
            }
            className="w-full accent-violet-600"
          />
          <div className="flex justify-between text-xs text-zinc-500 mt-1">
            <span>40% (liberal)</span>
            <span>95% (strict)</span>
          </div>
          <p className="text-xs text-zinc-500 mt-1.5">{t("confidenceHint")}</p>
        </div>
      </Card>

      {/* Language Mode */}
      <Card>
        <h3 className="text-sm font-semibold text-zinc-200 mb-3">
          🌐 {t("languageModeLabel")}
        </h3>
        <div className="space-y-2">
          {(["auto", "uz", "ru"] as const).map((mode) => (
            <label key={mode} className="flex items-center gap-3 cursor-pointer group">
              <div
                onClick={() => setSettings({ ...settings, language_mode: mode })}
                className={`w-4 h-4 rounded-full border-2 transition-colors flex items-center justify-center ${
                  settings.language_mode === mode
                    ? "border-violet-600 bg-violet-600"
                    : "border-zinc-600 group-hover:border-zinc-400"
                }`}
              >
                {settings.language_mode === mode && (
                  <div className="w-1.5 h-1.5 rounded-full bg-white" />
                )}
              </div>
              <span className="text-sm text-zinc-300">
                {t(`languageModes.${mode}` as Parameters<typeof t>[0])}
              </span>
            </label>
          ))}
        </div>
      </Card>

      {/* Banned Topics */}
      <Card>
        <h3 className="text-sm font-semibold text-zinc-200 mb-1">
          🚫 {t("bannedTopicsLabel")}
        </h3>
        <p className="text-xs text-zinc-500 mb-3">{t("bannedTopicsHint")}</p>
        <div className="flex flex-wrap gap-2 mb-3">
          {settings.banned_topics.map((topic) => (
            <span
              key={topic}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-red-900/30 text-red-400 border border-red-900/40"
            >
              {topic}
              <button
                onClick={() => removeTopic(topic)}
                className="hover:text-red-300 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            placeholder={t("bannedTopicsPlaceholder")}
            value={topicInput}
            onChange={(e) => setTopicInput(e.target.value)}
            onKeyDown={handleTopicKey}
            className="flex-1"
          />
          <Button variant="secondary" onClick={addTopic} disabled={!topicInput.trim()}>
            + {tc("add")}
          </Button>
        </div>
      </Card>

      {/* Save */}
      <div className="flex items-center gap-3">
        <Button onClick={handleSave} disabled={saving} className="min-w-32">
          {saving ? (
            <span className="flex items-center gap-2">
              <Spinner size={14} />
              {t("saving")}
            </span>
          ) : saved ? (
            t("saved")
          ) : (
            t("save")
          )}
        </Button>
      </div>
    </div>
  );
}
