"use client";

import { useState, useEffect } from "react";
import { type Node } from "reactflow";
import { useTranslations } from "next-intl";

interface Props {
  node: Node;
  onSave: (data: Record<string, unknown>) => void;
  onClose: () => void;
}

export default function NodeConfigDrawer({ node, onSave, onClose }: Props) {
  const t = useTranslations("flows.config");
  const [form, setForm] = useState<Record<string, unknown>>(node.data || {});

  useEffect(() => {
    setForm(node.data || {});
  }, [node.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const ntype = (node.data?.nodeType as string) || node.type;

  const set = (key: string, value: unknown) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="w-72 border-l bg-card flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <p className="font-semibold text-sm">
          {t(`title.${ntype}` as Parameters<typeof t>[0])}
        </p>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition text-lg leading-none"
        >
          ✕
        </button>
      </div>

      {/* Config body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* ── MESSAGE ── */}
        {ntype === "message" && (
          <>
            <Field label={t("message_text")}>
              <textarea
                rows={5}
                value={(form.text as string) || ""}
                onChange={(e) => set("text", e.target.value)}
                placeholder={t("message_placeholder")}
                className="w-full text-sm bg-muted rounded-md p-2.5 outline-none resize-none leading-relaxed"
              />
            </Field>
            <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-2.5 leading-relaxed">
              💡 {t("interpolate_hint")}
            </p>
          </>
        )}

        {/* ── CONDITION ── */}
        {ntype === "condition" && (
          <>
            <Field label={t("variable")}>
              <input
                value={(form.variable as string) || ""}
                onChange={(e) => set("variable", e.target.value)}
                placeholder="order_status_result.status"
                className="w-full text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
              />
            </Field>
            <Field label={t("operator")}>
              <select
                value={(form.operator as string) || "eq"}
                onChange={(e) => set("operator", e.target.value)}
                className="w-full text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
              >
                <option value="eq">= (teng)</option>
                <option value="neq">≠ (teng emas)</option>
                <option value="contains">∋ (ichida bor)</option>
                <option value="gt">&gt; (katta)</option>
                <option value="lt">&lt; (kichik)</option>
                <option value="exists">mavjud</option>
              </select>
            </Field>
            <Field label={t("value")}>
              <input
                value={(form.value as string) || ""}
                onChange={(e) => set("value", e.target.value)}
                placeholder="delivered"
                className="w-full text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
              />
            </Field>
            <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-2.5">
              💡 <b>true</b> / <b>false</b> chiqish chiziqlarini ulang.
            </p>
          </>
        )}

        {/* ── ACTION ── */}
        {ntype === "action" && (
          <>
            <Field label={t("action_name")}>
              <input
                value={(form.action_name as string) || ""}
                onChange={(e) => set("action_name", e.target.value)}
                placeholder="order_status"
                className="w-full text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none font-mono"
              />
            </Field>
            <Field label={t("params_json")}>
              <textarea
                rows={5}
                value={
                  typeof form.params === "object"
                    ? JSON.stringify(form.params, null, 2)
                    : ((form.params as string) ?? "{}")
                }
                onChange={(e) => {
                  try {
                    set("params", JSON.parse(e.target.value));
                  } catch {
                    set("params", e.target.value);
                  }
                }}
                className="w-full text-xs bg-muted rounded-md p-2.5 outline-none resize-none font-mono leading-relaxed"
              />
            </Field>
            <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-2.5">
              💡 Natija <code>{"{{action_name_result}}"}</code> sifatida
              keyingi tugunlarda ishlatiladi.
            </p>
          </>
        )}

        {/* ── WAIT ── */}
        {ntype === "wait" && (
          <Field label={t("delay_seconds")}>
            <input
              type="number"
              min={0}
              max={86400}
              value={(form.delay_seconds as number) ?? 0}
              onChange={(e) => set("delay_seconds", Number(e.target.value))}
              className="w-full text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
            />
          </Field>
        )}

        {/* ── TRIGGER ── */}
        {ntype === "trigger" && (
          <p className="text-sm text-muted-foreground">
            Trigger sozlamalari flow boshida (yuqori panelda) o'zgartiriladi.
          </p>
        )}

        {/* ── END ── */}
        {ntype === "end" && (
          <p className="text-sm text-muted-foreground">
            Bu tugun flow'ni tugatadi. Hech narsa sozlanmaydi.
          </p>
        )}
      </div>

      {/* Footer */}
      {!["trigger", "end"].includes(ntype) && (
        <div className="p-4 border-t">
          <button
            onClick={() => onSave(form)}
            className="w-full bg-primary text-primary-foreground rounded-lg py-2 text-sm font-medium hover:bg-primary/90 transition"
          >
            {t("save_node")}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Helper ──────────────────────────────────────────────────────────────────
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
