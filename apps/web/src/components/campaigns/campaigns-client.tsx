"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";
import { apiClient } from "@/lib/api-client";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Campaign {
  id: string;
  name: string;
  campaign_type: string;
  status: string;
  segment_id: string | null;
  template: Record<string, unknown>;
  scheduled_at: string | null;
  sent_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  created_at: string;
}

interface Segment {
  id: string;
  name: string;
  filters: Record<string, unknown>;
}

interface Product {
  id: string;
  name: string;
  price_uzs: number;
  description: string | null;
  image_url: string | null;
  checkout_url: string | null;
  in_stock: boolean;
  is_active: boolean;
}

interface DripSequence {
  id: string;
  name: string;
  trigger_type: string;
  is_active: boolean;
  steps: Array<{
    id: string;
    step_order: number;
    step_type: string;
    config: Record<string, unknown>;
    wait_minutes: number | null;
  }>;
}

// ─── Status badge ─────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-zinc-700 text-zinc-300",
  scheduled: "bg-blue-900 text-blue-300",
  running: "bg-green-900 text-green-300",
  paused: "bg-yellow-900 text-yellow-300",
  completed: "bg-purple-900 text-purple-300",
  failed: "bg-red-900 text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] ?? "bg-zinc-700 text-zinc-300"}`}>
      {status}
    </span>
  );
}

// ─── Campaign Modal ────────────────────────────────────────────────────────

function CampaignModal({
  campaign,
  segments,
  onClose,
  onSave,
}: {
  campaign: Campaign | null;
  segments: Segment[];
  onClose: () => void;
  onSave: () => void;
}) {
  const t = useTranslations("campaigns");
  const [name, setName] = useState(campaign?.name ?? "");
  const [segmentId, setSegmentId] = useState(campaign?.segment_id ?? "");
  const [templateText, setTemplateText] = useState(
    (campaign?.template?.text as string) ?? ""
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!name.trim()) {
      setError(t("nameRequired"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const body = {
        name,
        campaign_type: "broadcast",
        segment_id: segmentId || null,
        template: { text: templateText },
      };
      if (campaign) {
        await apiClient.put(`/growth/campaigns/${campaign.id}`, body);
      } else {
        await apiClient.post("/growth/campaigns", body);
      }
      onSave();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl bg-zinc-900 border border-zinc-800 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">
          {campaign ? t("editCampaign") : t("newCampaign")}
        </h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("campaignName")}</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("namePlaceholder")} />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("segment")}</label>
            <select
              value={segmentId}
              onChange={(e) => setSegmentId(e.target.value)}
              className="w-full rounded-lg bg-zinc-800 border border-zinc-700 text-white px-3 py-2 text-sm"
            >
              <option value="">{t("noSegment")}</option>
              {segments.map((seg) => (
                <option key={seg.id} value={seg.id}>{seg.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("messageText")}</label>
            <textarea
              value={templateText}
              onChange={(e) => setTemplateText(e.target.value)}
              rows={4}
              className="w-full rounded-lg bg-zinc-800 border border-zinc-700 text-white px-3 py-2 text-sm resize-none"
              placeholder={t("messageTextPlaceholder")}
            />
          </div>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>{t("cancel")}</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Spinner size="sm" /> : t("save")}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Segment Modal ─────────────────────────────────────────────────────────

function SegmentModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: () => void;
}) {
  const t = useTranslations("campaigns");
  const [name, setName] = useState("");
  const [optInOnly, setOptInOnly] = useState(true);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await apiClient.post("/growth/segments", {
        name,
        filters: { opt_in: optInOnly },
      });
      onSave();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-xl bg-zinc-900 border border-zinc-800 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">{t("newSegment")}</h2>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">{t("segmentName")}</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("segmentNamePlaceholder")} />
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
          <input
            type="checkbox"
            checked={optInOnly}
            onChange={(e) => setOptInOnly(e.target.checked)}
            className="rounded"
          />
          {t("optInOnly")}
        </label>

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>{t("cancel")}</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Spinner size="sm" /> : t("create")}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Product Modal ─────────────────────────────────────────────────────────

function ProductModal({
  product,
  onClose,
  onSave,
}: {
  product: Product | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const t = useTranslations("campaigns");
  const [name, setName] = useState(product?.name ?? "");
  const [price, setPrice] = useState(product ? String(product.price_uzs) : "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [checkoutUrl, setCheckoutUrl] = useState(product?.checkout_url ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim() || !price) return;
    setSaving(true);
    try {
      const body = {
        name,
        price_uzs: parseInt(price, 10),
        description: description || null,
        checkout_url: checkoutUrl || null,
        in_stock: true,
      };
      if (product) {
        await apiClient.put(`/growth/products/${product.id}`, body);
      } else {
        await apiClient.post("/growth/products", body);
      }
      onSave();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl bg-zinc-900 border border-zinc-800 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">
          {product ? t("editProduct") : t("newProduct")}
        </h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("productName")}</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("priceUzs")}</label>
            <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="500000" />
          </div>
          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("description")}</label>
            <Input value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-zinc-400 mb-1">{t("checkoutUrl")}</label>
            <Input value={checkoutUrl} onChange={(e) => setCheckoutUrl(e.target.value)} placeholder="https://example.uz/buy/..." />
          </div>
        </div>

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>{t("cancel")}</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Spinner size="sm" /> : t("save")}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────

type Tab = "campaigns" | "segments" | "products" | "drip";

export function CampaignsClient() {
  const t = useTranslations("campaigns");
  const [tab, setTab] = useState<Tab>("campaigns");

  // Campaigns
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null);

  // Segments
  const [segments, setSegments] = useState<Segment[]>([]);
  const [showSegmentModal, setShowSegmentModal] = useState(false);

  // Products
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [showProductModal, setShowProductModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Drip
  const [drips, setDrips] = useState<DripSequence[]>([]);
  const [dripsLoading, setDripsLoading] = useState(false);

  const loadCampaigns = useCallback(async () => {
    setCampaignsLoading(true);
    try {
      const [campRes, segRes] = await Promise.all([
        apiClient.get<Campaign[]>("/growth/campaigns"),
        apiClient.get<Segment[]>("/growth/segments"),
      ]);
      setCampaigns(campRes.data ?? []);
      setSegments(segRes.data ?? []);
    } finally {
      setCampaignsLoading(false);
    }
  }, []);

  const loadProducts = useCallback(async () => {
    setProductsLoading(true);
    try {
      const res = await apiClient.get<Product[]>("/growth/products");
      setProducts(res.data ?? []);
    } finally {
      setProductsLoading(false);
    }
  }, []);

  const loadDrips = useCallback(async () => {
    setDripsLoading(true);
    try {
      const res = await apiClient.get<DripSequence[]>("/growth/drip-sequences");
      setDrips(res.data ?? []);
    } finally {
      setDripsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  useEffect(() => {
    if (tab === "products") loadProducts();
    if (tab === "drip") loadDrips();
  }, [tab, loadProducts, loadDrips]);

  const handleCampaignAction = async (id: string, action: "send-now" | "pause" | "cancel") => {
    try {
      await apiClient.post(`/growth/campaigns/${id}/${action}`);
      await loadCampaigns();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Xatolik");
    }
  };

  const handleDeleteCampaign = async (id: string) => {
    if (!confirm(t("confirmDelete"))) return;
    await apiClient.delete(`/growth/campaigns/${id}`);
    await loadCampaigns();
  };

  const handleToggleDrip = async (seq: DripSequence) => {
    const action = seq.is_active ? "deactivate" : "activate";
    await apiClient.post(`/growth/drip-sequences/${seq.id}/${action}`);
    await loadDrips();
  };

  const handleDeleteDrip = async (id: string) => {
    if (!confirm(t("confirmDelete"))) return;
    await apiClient.delete(`/growth/drip-sequences/${id}`);
    await loadDrips();
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "campaigns", label: t("tabCampaigns") },
    { key: "segments", label: t("tabSegments") },
    { key: "products", label: t("tabProducts") },
    { key: "drip", label: t("tabDrip") },
  ];

  return (
    <div className="space-y-6">
      {/* Tab nav */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-violet-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Campaigns tab ── */}
      {tab === "campaigns" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => { setEditingCampaign(null); setShowCampaignModal(true); }}>
              + {t("newCampaign")}
            </Button>
          </div>

          {campaignsLoading ? (
            <div className="flex justify-center py-12"><Spinner /></div>
          ) : campaigns.length === 0 ? (
            <Card className="p-8 text-center text-zinc-500">{t("noCampaigns")}</Card>
          ) : (
            <div className="space-y-3">
              {campaigns.map((camp) => (
                <Card key={camp.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-white">{camp.name}</span>
                        <StatusBadge status={camp.status} />
                        <span className="text-xs text-zinc-500 capitalize">{camp.campaign_type}</span>
                      </div>
                      {/* Metrics */}
                      {camp.status !== "draft" && (
                        <div className="flex gap-4 text-xs text-zinc-400 mt-1">
                          <span>📤 {camp.sent_count} {t("sent")}</span>
                          <span>✅ {camp.delivered_count} {t("delivered")}</span>
                          <span>👁 {camp.read_count} {t("read")}</span>
                          {camp.failed_count > 0 && (
                            <span className="text-red-400">❌ {camp.failed_count} {t("failed")}</span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {camp.status === "draft" && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => { setEditingCampaign(camp); setShowCampaignModal(true); }}
                          >
                            {t("edit")}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleCampaignAction(camp.id, "send-now")}
                          >
                            {t("sendNow")}
                          </Button>
                        </>
                      )}
                      {camp.status === "running" && (
                        <Button size="sm" variant="ghost" onClick={() => handleCampaignAction(camp.id, "pause")}>
                          {t("pause")}
                        </Button>
                      )}
                      {camp.status === "paused" && (
                        <Button size="sm" onClick={() => handleCampaignAction(camp.id, "send-now")}>
                          {t("resume")}
                        </Button>
                      )}
                      {["draft", "scheduled", "paused"].includes(camp.status) && (
                        <Button size="sm" variant="ghost" onClick={() => handleDeleteCampaign(camp.id)}>
                          🗑
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Segments tab ── */}
      {tab === "segments" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowSegmentModal(true)}>+ {t("newSegment")}</Button>
          </div>
          {segments.length === 0 ? (
            <Card className="p-8 text-center text-zinc-500">{t("noSegments")}</Card>
          ) : (
            <div className="space-y-3">
              {segments.map((seg) => (
                <Card key={seg.id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">{seg.name}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      {Object.entries(seg.filters).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ") || t("noFilters")}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      await apiClient.delete(`/growth/segments/${seg.id}`);
                      await loadCampaigns();
                    }}
                  >
                    🗑
                  </Button>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Products tab ── */}
      {tab === "products" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => { setEditingProduct(null); setShowProductModal(true); }}>
              + {t("newProduct")}
            </Button>
          </div>
          {productsLoading ? (
            <div className="flex justify-center py-12"><Spinner /></div>
          ) : products.length === 0 ? (
            <Card className="p-8 text-center text-zinc-500">{t("noProducts")}</Card>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {products.map((prod) => (
                <Card key={prod.id} className="p-4 space-y-2">
                  <div className="flex items-start justify-between">
                    <span className="font-medium text-white">{prod.name}</span>
                    <span className={`text-xs rounded-full px-2 py-0.5 ${prod.in_stock ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
                      {prod.in_stock ? t("inStock") : t("outOfStock")}
                    </span>
                  </div>
                  <p className="text-lg font-semibold text-violet-400">
                    {prod.price_uzs.toLocaleString()} UZS
                  </p>
                  {prod.description && (
                    <p className="text-xs text-zinc-400 line-clamp-2">{prod.description}</p>
                  )}
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => { setEditingProduct(prod); setShowProductModal(true); }}>
                      {t("edit")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await apiClient.delete(`/growth/products/${prod.id}`);
                        await loadProducts();
                      }}
                    >
                      🗑
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Drip tab ── */}
      {tab === "drip" && (
        <div className="space-y-4">
          <p className="text-zinc-400 text-sm">{t("dripDescription")}</p>
          {dripsLoading ? (
            <div className="flex justify-center py-12"><Spinner /></div>
          ) : drips.length === 0 ? (
            <Card className="p-8 text-center text-zinc-500">{t("noDrips")}</Card>
          ) : (
            <div className="space-y-3">
              {drips.map((seq) => (
                <Card key={seq.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{seq.name}</span>
                        <span className={`text-xs rounded-full px-2 py-0.5 ${seq.is_active ? "bg-green-900 text-green-300" : "bg-zinc-700 text-zinc-400"}`}>
                          {seq.is_active ? t("active") : t("inactive")}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500 mt-1">
                        {t("trigger")}: {seq.trigger_type} · {seq.steps.length} {t("steps")}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => handleToggleDrip(seq)}>
                        {seq.is_active ? t("deactivate") : t("activate")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => handleDeleteDrip(seq.id)}>🗑</Button>
                    </div>
                  </div>
                  {seq.steps.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {seq.steps.map((step) => (
                        <div key={step.id} className="flex items-center gap-2 text-xs text-zinc-400">
                          <span className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-zinc-300 shrink-0">
                            {step.step_order}
                          </span>
                          <span className="capitalize">{step.step_type}</span>
                          {step.wait_minutes && (
                            <span>· {step.wait_minutes >= 60 ? `${step.wait_minutes / 60}h` : `${step.wait_minutes}min`}</span>
                          )}
                          {step.config?.text && (
                            <span className="truncate text-zinc-500">· "{String(step.config.text).slice(0, 40)}"</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {showCampaignModal && (
        <CampaignModal
          campaign={editingCampaign}
          segments={segments}
          onClose={() => setShowCampaignModal(false)}
          onSave={() => { setShowCampaignModal(false); loadCampaigns(); }}
        />
      )}
      {showSegmentModal && (
        <SegmentModal
          onClose={() => setShowSegmentModal(false)}
          onSave={() => { setShowSegmentModal(false); loadCampaigns(); }}
        />
      )}
      {showProductModal && (
        <ProductModal
          product={editingProduct}
          onClose={() => setShowProductModal(false)}
          onSave={() => { setShowProductModal(false); loadProducts(); }}
        />
      )}
    </div>
  );
}
