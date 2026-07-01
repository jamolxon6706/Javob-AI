"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";

interface TenantAction {
  id: string;
  name: string;
  display_name: string;
  description: string;
  action_type: string;
  is_active: boolean;
}

const BUILTIN_TEMPLATES = [
  {
    name: "order_status",
    display_name: "Buyurtma holati",
    description:
      "Buyurtma ID bo'yicha holat tekshiradi. Xaridor '123-buyurtmam qani?' deb so'raganda ishlaydi.",
    params_schema: {
      type: "object",
      properties: {
        order_id: {
          type: "string",
          description: "Buyurtma ID raqami",
        },
      },
      required: ["order_id"],
    },
    action_type: "builtin",
    icon: "📦",
  },
  {
    name: "book_appointment",
    display_name: "Uchrashuv band qilish",
    description:
      "Xaridordan ism, telefon va sana olib uchrashuv band qiladi.",
    params_schema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Ism" },
        phone: { type: "string", description: "Telefon raqam" },
        date: { type: "string", description: "Sana (YYYY-MM-DD)" },
      },
      required: ["name", "phone"],
    },
    action_type: "builtin",
    icon: "📅",
  },
  {
    name: "collect_lead",
    display_name: "Lead yig'ish",
    description:
      "Xaridor ma'lumotlarini (ism, telefon, email) CRM ga saqlaydi.",
    params_schema: {
      type: "object",
      properties: {
        name: { type: "string" },
        phone: { type: "string" },
        email: { type: "string" },
      },
      required: ["name"],
    },
    action_type: "builtin",
    icon: "👤",
  },
];

const emptyWebhookForm = {
  name: "",
  display_name: "",
  description: "",
  webhook_url: "",
  webhook_secret: "",
};

export default function ActionsPage() {
  const t = useTranslations("actions");
  const [actions, setActions] = useState<TenantAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [showWebhookForm, setShowWebhookForm] = useState(false);
  const [webhookForm, setWebhookForm] = useState(emptyWebhookForm);
  const [saving, setSaving] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, unknown>>({});
  const [testingId, setTestingId] = useState<string | null>(null);

  const load = async () => {
    const r = await apiClient.get("/actions");
    setActions(r.data);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const addBuiltin = async (tpl: (typeof BUILTIN_TEMPLATES)[0]) => {
    await apiClient.post("/actions", {
      name: tpl.name,
      display_name: tpl.display_name,
      description: tpl.description,
      params_schema: tpl.params_schema,
      action_type: tpl.action_type,
    });
    await load();
  };

  const addWebhook = async () => {
    setSaving(true);
    try {
      await apiClient.post("/actions", {
        ...webhookForm,
        params_schema: { type: "object", properties: {}, required: [] },
        action_type: "webhook",
      });
      setShowWebhookForm(false);
      setWebhookForm(emptyWebhookForm);
      await load();
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (action: TenantAction) => {
    await apiClient.patch(`/actions/${action.id}`, {
      is_active: !action.is_active,
    });
    setActions((prev) =>
      prev.map((a) =>
        a.id === action.id ? { ...a, is_active: !a.is_active } : a
      )
    );
  };

  const remove = async (id: string) => {
    if (!confirm(t("delete_confirm"))) return;
    await apiClient.delete(`/actions/${id}`);
    setActions((prev) => prev.filter((a) => a.id !== id));
  };

  const testAction = async (action: TenantAction) => {
    setTestingId(action.id);
    try {
      const r = await apiClient.post(`/actions/${action.id}/test`, {});
      setTestResults((prev) => ({ ...prev, [action.id]: r.data.output }));
    } catch (e) {
      setTestResults((prev) => ({ ...prev, [action.id]: { error: String(e) } }));
    } finally {
      setTestingId(null);
    }
  };

  const existingNames = new Set(actions.map((a) => a.name));

  if (loading) {
    return (
      <div className="p-8 text-center text-muted-foreground">{t("loading")}</div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-muted-foreground text-sm mt-1">{t("subtitle")}</p>
      </div>

      {/* Built-in templates */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          {t("builtins")}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {BUILTIN_TEMPLATES.map((tpl) => {
            const added = existingNames.has(tpl.name);
            return (
              <div
                key={tpl.name}
                className="border rounded-xl p-4 bg-card flex flex-col"
              >
                <div className="text-2xl mb-2">{tpl.icon}</div>
                <p className="font-medium text-sm">{tpl.display_name}</p>
                <p className="text-xs text-muted-foreground mt-1 flex-1">
                  {tpl.description}
                </p>
                <button
                  onClick={() => !added && addBuiltin(tpl)}
                  disabled={added}
                  className={`mt-3 w-full text-xs rounded-lg py-1.5 font-medium transition ${
                    added
                      ? "bg-muted text-muted-foreground cursor-default"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  }`}
                >
                  {added ? `✓ ${t("added")}` : t("add")}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* Webhook action */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            {t("webhook_actions")}
          </h2>
          <button
            onClick={() => setShowWebhookForm((v) => !v)}
            className="text-xs text-primary hover:underline"
          >
            {showWebhookForm ? t("cancel") : `+ ${t("add_webhook")}`}
          </button>
        </div>

        {showWebhookForm && (
          <div className="border rounded-xl p-5 bg-card space-y-3 mb-4">
            <div className="grid grid-cols-2 gap-3">
              <FormField label={t("action_name")}>
                <input
                  value={webhookForm.name}
                  onChange={(e) =>
                    setWebhookForm({ ...webhookForm, name: e.target.value })
                  }
                  placeholder="get_product_info"
                  className="w-full mt-1 text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none font-mono"
                />
              </FormField>
              <FormField label={t("display_name")}>
                <input
                  value={webhookForm.display_name}
                  onChange={(e) =>
                    setWebhookForm({
                      ...webhookForm,
                      display_name: e.target.value,
                    })
                  }
                  className="w-full mt-1 text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
                />
              </FormField>
            </div>
            <FormField label={t("description")}>
              <input
                value={webhookForm.description}
                onChange={(e) =>
                  setWebhookForm({
                    ...webhookForm,
                    description: e.target.value,
                  })
                }
                placeholder="Mahsulot ma'lumotlarini ID bo'yicha qaytaradi"
                className="w-full mt-1 text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
              />
            </FormField>
            <FormField label={t("webhook_url")}>
              <input
                value={webhookForm.webhook_url}
                onChange={(e) =>
                  setWebhookForm({
                    ...webhookForm,
                    webhook_url: e.target.value,
                  })
                }
                placeholder="https://your-api.com/webhooks/javobai"
                className="w-full mt-1 text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
              />
            </FormField>
            <FormField label={`${t("webhook_secret")} (${t("optional")})`}>
              <input
                type="password"
                value={webhookForm.webhook_secret}
                onChange={(e) =>
                  setWebhookForm({
                    ...webhookForm,
                    webhook_secret: e.target.value,
                  })
                }
                className="w-full mt-1 text-sm bg-muted rounded-md px-2.5 py-1.5 outline-none"
              />
            </FormField>
            <div className="flex gap-2 pt-1">
              <button
                onClick={addWebhook}
                disabled={
                  saving || !webhookForm.name || !webhookForm.webhook_url
                }
                className="bg-primary text-primary-foreground text-xs px-4 py-1.5 rounded-md disabled:opacity-50 font-medium"
              >
                {saving ? t("saving") : t("save")}
              </button>
              <button
                onClick={() => {
                  setShowWebhookForm(false);
                  setWebhookForm(emptyWebhookForm);
                }}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {t("cancel")}
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Active actions list */}
      {actions.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            {t("your_actions")}
          </h2>
          <div className="space-y-2">
            {actions.map((action) => (
              <div key={action.id} className="border rounded-xl bg-card overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                        {action.name}
                      </code>
                      <span className="text-sm font-medium">
                        {action.display_name}
                      </span>
                      <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                        {action.action_type}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {action.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        action.is_active
                          ? "bg-green-500/10 text-green-500"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {action.is_active ? t("active") : t("inactive")}
                    </span>
                    <button
                      onClick={() => testAction(action)}
                      disabled={testingId === action.id}
                      className="text-xs text-muted-foreground hover:text-foreground transition disabled:opacity-50"
                    >
                      {testingId === action.id ? "..." : "Test"}
                    </button>
                    <button
                      onClick={() => toggle(action)}
                      className="text-xs text-muted-foreground hover:text-foreground transition"
                    >
                      {action.is_active ? t("disable") : t("enable")}
                    </button>
                    <button
                      onClick={() => remove(action.id)}
                      className="text-xs text-destructive hover:underline"
                    >
                      {t("delete")}
                    </button>
                  </div>
                </div>

                {/* Test result */}
                {testResults[action.id] && (
                  <div className="border-t bg-muted/30 px-4 py-3">
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Test natijasi:
                    </p>
                    <pre className="text-xs font-mono text-foreground whitespace-pre-wrap">
                      {JSON.stringify(testResults[action.id], null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
