"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";

interface Flow {
  id: string;
  name: string;
  trigger_type: string;
  is_active: boolean;
  created_at: string;
}

const TRIGGER_ICONS: Record<string, string> = {
  first_contact: "👋",
  keyword: "🔑",
  action_result: "⚡",
  schedule: "🕐",
};

export default function FlowsPage() {
  const t = useTranslations("flows");
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/flows").then((r) => {
      setFlows(r.data);
      setLoading(false);
    });
  }, []);

  const toggleActive = async (flow: Flow) => {
    const endpoint = flow.is_active
      ? `/flows/${flow.id}/deactivate`
      : `/flows/${flow.id}/activate`;
    await apiClient.post(endpoint);
    setFlows((prev) =>
      prev.map((f) =>
        f.id === flow.id ? { ...f, is_active: !f.is_active } : f
      )
    );
  };

  const deleteFlow = async (id: string) => {
    if (!confirm(t("delete_confirm"))) return;
    await apiClient.delete(`/flows/${id}`);
    setFlows((prev) => prev.filter((f) => f.id !== id));
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-muted-foreground">{t("loading")}</div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">{t("subtitle")}</p>
        </div>
        <Link
          href="flows/new"
          className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition"
        >
          + {t("create")}
        </Link>
      </div>

      {flows.length === 0 ? (
        <div className="border border-dashed rounded-xl p-16 text-center">
          <p className="text-4xl mb-4">🔀</p>
          <p className="text-muted-foreground">{t("empty")}</p>
          <Link
            href="flows/new"
            className="mt-4 inline-block text-primary underline text-sm"
          >
            {t("create_first")}
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {flows.map((flow) => (
            <div
              key={flow.id}
              className="flex items-center justify-between bg-card border rounded-xl px-5 py-4"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">
                  {TRIGGER_ICONS[flow.trigger_type] ?? "🔀"}
                </span>
                <div>
                  <p className="font-medium">{flow.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {t(`trigger.${flow.trigger_type}`)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs px-2 py-1 rounded-full font-medium ${
                    flow.is_active
                      ? "bg-green-500/10 text-green-500"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {flow.is_active ? t("active") : t("inactive")}
                </span>
                <button
                  onClick={() => toggleActive(flow)}
                  className="text-xs text-muted-foreground hover:text-foreground transition"
                >
                  {flow.is_active ? t("deactivate") : t("activate")}
                </button>
                <Link
                  href={`flows/${flow.id}`}
                  className="text-xs text-primary hover:underline"
                >
                  {t("edit")}
                </Link>
                <button
                  onClick={() => deleteFlow(flow.id)}
                  className="text-xs text-destructive hover:underline"
                >
                  {t("delete")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
