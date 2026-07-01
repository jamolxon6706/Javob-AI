"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";

interface Rule {
  id: string;
  tenant_id: string;
  name: string;
  trigger_type: string;
  trigger_value: Record<string, unknown>;
  action_type: string;
  action_value: Record<string, unknown>;
  priority: number;
  is_active: boolean;
}

const TRIGGER_TYPES = [
  "keyword",
  "out_of_hours",
  "stop_word",
  "comment_to_dm",
  "first_contact",
] as const;

const ACTION_TYPES = ["reply", "handoff", "assign", "silence"] as const;

function RuleModal({
  rule,
  onClose,
  onSave,
}: {
  rule: Rule | null;
  onClose: () => void;
  onSave: (saved: Rule) => void;
}) {
  const t = useTranslations("rules");
  const tc = useTranslations("common");
  const [name, setName] = useState(rule?.name ?? "");
  const [triggerType, setTriggerType] = useState<string>(
    rule?.trigger_type ?? "keyword"
  );
  const [keywords, setKeywords] = useState<string>(
    (rule?.trigger_value?.keywords as string[])?.join(", ") ?? ""
  );
  const [actionType, setActionType] = useState<string>(
    rule?.action_type ?? "reply"
  );
  const [replyText, setReplyText] = useState<string>(
    (rule?.action_value?.text as string) ?? ""
  );
  const [priority, setPriority] = useState(rule?.priority ?? 0);
  const [isActive, setIsActive] = useState(rule?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);

    const trigger_value: Record<string, unknown> =
      triggerType === "keyword"
        ? { keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean) }
        : {};
    const action_value: Record<string, unknown> =
      actionType === "reply" ? { text: replyText } : {};

    try {
      const method = rule ? "PATCH" : "POST";
      const url = rule ? `/api/proxy/rules/${rule.id}` : "/api/proxy/rules";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          trigger_type: triggerType,
          trigger_value,
          action_type: actionType,
          action_value,
          priority,
          is_active: isActive,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? tc("error"));
      onSave(data as Rule);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tc("error"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card className="w-full max-w-lg">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-zinc-100">
            {rule ? t("ruleModal.editTitle") : t("ruleModal.createTitle")}
          </h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 text-xl leading-none">×</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">
              {t("ruleModal.nameLabel")}
            </label>
            <Input
              placeholder={t("ruleModal.namePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("ruleModal.triggerLabel")}
              </label>
              <select
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600"
                value={triggerType}
                onChange={(e) => setTriggerType(e.target.value)}
              >
                {TRIGGER_TYPES.map((tt) => (
                  <option key={tt} value={tt}>
                    {t(`triggerType.${tt}` as Parameters<typeof t>[0])}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                Harakat
              </label>
              <select
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600"
                value={actionType}
                onChange={(e) => setActionType(e.target.value)}
              >
                {ACTION_TYPES.map((at) => (
                  <option key={at} value={at}>
                    {t(`actionType.${at}` as Parameters<typeof t>[0])}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {triggerType === "keyword" && (
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("ruleModal.keywordLabel")}
              </label>
              <Input
                placeholder={t("ruleModal.keywordPlaceholder")}
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </div>
          )}

          {actionType === "reply" && (
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("ruleModal.replyTextLabel")}
              </label>
              <textarea
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600 resize-none"
                rows={3}
                placeholder={t("ruleModal.replyTextPlaceholder")}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
              />
            </div>
          )}

          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("ruleModal.priorityLabel")}
              </label>
              <Input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="w-24"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer mt-5">
              <div
                onClick={() => setIsActive(!isActive)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  isActive ? "bg-violet-600" : "bg-zinc-700"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                    isActive ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </div>
              <span className="text-sm text-zinc-300">{t("ruleModal.activeLabel")}</span>
            </label>
          </div>

          {error && <p className="text-xs text-red-400">{error}</p>}

          <div className="flex gap-2 pt-1">
            <Button variant="secondary" onClick={onClose} className="flex-1" disabled={saving}>
              {tc("cancel")}
            </Button>
            <Button onClick={handleSave} className="flex-1" disabled={saving || !name.trim()}>
              {saving ? t("ruleModal.saving" as Parameters<typeof t>[0]) : t("ruleModal.save" as Parameters<typeof t>[0])}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

const TRIGGER_ICONS: Record<string, string> = {
  keyword: "🔑",
  out_of_hours: "🌙",
  stop_word: "🚫",
  comment_to_dm: "💬",
  first_contact: "👋",
};

function RuleRow({
  rule,
  onEdit,
  onDelete,
  onToggle,
}: {
  rule: Rule;
  onEdit: (r: Rule) => void;
  onDelete: (id: string) => void;
  onToggle: (r: Rule) => void;
}) {
  const t = useTranslations("rules");
  const tc = useTranslations("common");
  const icon = TRIGGER_ICONS[rule.trigger_type] ?? "⚡";

  return (
    <div className="flex items-center gap-3 p-4 rounded-xl border border-zinc-800 bg-zinc-900/60 group hover:border-zinc-700 transition-colors">
      <span className="text-lg">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-zinc-100">{rule.name}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
            {t(`triggerType.${rule.trigger_type}` as Parameters<typeof t>[0])}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-violet-900/30 text-violet-400">
            {t(`actionType.${rule.action_type}` as Parameters<typeof t>[0])}
          </span>
        </div>
        {rule.trigger_value?.keywords && (
          <p className="text-xs text-zinc-500 truncate">
            {(rule.trigger_value.keywords as string[]).join(", ")}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <div
          onClick={() => onToggle(rule)}
          className={`relative w-9 h-5 rounded-full transition-colors cursor-pointer ${
            rule.is_active ? "bg-violet-600" : "bg-zinc-700"
          }`}
        >
          <div
            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              rule.is_active ? "translate-x-4" : "translate-x-0.5"
            }`}
          />
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button variant="ghost" onClick={() => onEdit(rule)} className="px-2 py-1 text-xs">
            {tc("edit")}
          </Button>
          <Button
            variant="ghost"
            onClick={() => onDelete(rule.id)}
            className="px-2 py-1 text-xs text-red-400 hover:text-red-300"
          >
            {tc("delete")}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function RulesClient() {
  const t = useTranslations("rules");
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Rule | null | "new">(null);

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/rules");
      if (res.ok) setRules(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  async function handleDelete(id: string) {
    if (!confirm(t("deleteConfirm"))) return;
    await fetch(`/api/proxy/rules/${id}`, { method: "DELETE" });
    setRules((prev) => prev.filter((r) => r.id !== id));
  }

  async function handleToggle(rule: Rule) {
    const res = await fetch(`/api/proxy/rules/${rule.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !rule.is_active }),
    });
    if (res.ok) {
      const updated = await res.json();
      setRules((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    }
  }

  function handleSaved(saved: Rule) {
    setRules((prev) => {
      const idx = prev.findIndex((r) => r.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setEditing(null);
  }

  return (
    <div>
      <div className="flex justify-end mb-4">
        <Button onClick={() => setEditing("new")}>+ {t("addRule")}</Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : rules.length === 0 ? (
        <Card className="flex flex-col items-center py-16 text-center">
          <div className="text-4xl mb-3">⚡</div>
          <p className="text-zinc-300 font-medium">{t("noRules")}</p>
          <p className="text-zinc-500 text-sm mt-1">{t("noRulesHint")}</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <RuleRow
              key={rule.id}
              rule={rule}
              onEdit={setEditing}
              onDelete={handleDelete}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}

      {editing !== null && (
        <RuleModal
          rule={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSave={handleSaved}
        />
      )}
    </div>
  );
}
