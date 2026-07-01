"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";

interface FAQ {
  id: string;
  tenant_id: string;
  question: string;
  answer: string;
  category: string | null;
  language: string;
  is_active: boolean;
}

interface RAGHit {
  id: string;
  question: string;
  answer: string;
  category: string | null;
  language: string;
  score: number;
}

// ─── FAQ Modal ────────────────────────────────────────────────────────────────
function FAQModal({
  faq,
  onClose,
  onSave,
}: {
  faq: FAQ | null;
  onClose: () => void;
  onSave: (saved: FAQ) => void;
}) {
  const t = useTranslations("knowledgeBase");
  const tc = useTranslations("common");
  const [question, setQuestion] = useState(faq?.question ?? "");
  const [answer, setAnswer] = useState(faq?.answer ?? "");
  const [category, setCategory] = useState(faq?.category ?? "");
  const [language, setLanguage] = useState(faq?.language ?? "uz");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!question.trim() || !answer.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const method = faq ? "PATCH" : "POST";
      const url = faq ? `/api/proxy/faqs/${faq.id}` : "/api/proxy/faqs";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.trim(),
          answer: answer.trim(),
          category: category.trim() || null,
          language,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? tc("error"));
      onSave(data as FAQ);
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
            {faq ? t("faqModal.editTitle") : t("faqModal.createTitle")}
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">
              {t("faqModal.questionLabel")}
            </label>
            <Input
              placeholder={t("faqModal.questionPlaceholder")}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">
              {t("faqModal.answerLabel")}
            </label>
            <textarea
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600 resize-none"
              rows={4}
              placeholder={t("faqModal.answerPlaceholder")}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("faqModal.categoryLabel")}
              </label>
              <Input
                placeholder={t("faqModal.categoryPlaceholder")}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                {t("faqModal.languageLabel")}
              </label>
              <select
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="uz">{t("faqModal.langUz")}</option>
                <option value="ru">{t("faqModal.langRu")}</option>
              </select>
            </div>
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex gap-2 pt-1">
            <Button
              variant="secondary"
              onClick={onClose}
              className="flex-1"
              disabled={saving}
            >
              {tc("cancel")}
            </Button>
            <Button
              onClick={handleSave}
              className="flex-1"
              disabled={saving || !question.trim() || !answer.trim()}
            >
              {saving ? t("faqModal.saving") : t("faqModal.save")}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ─── RAG Test Panel ───────────────────────────────────────────────────────────
function RAGTestPanel() {
  const t = useTranslations("knowledgeBase");
  const [query, setQuery] = useState("");
  const [testing, setTesting] = useState(false);
  const [hits, setHits] = useState<RAGHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleTest() {
    if (!query.trim()) return;
    setTesting(true);
    setError(null);
    setHits(null);
    try {
      const res = await fetch("/api/proxy/internal/rag-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), top_k: 5 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Error");
      setHits(data.results as RAGHit[]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setTesting(false);
    }
  }

  function scoreLabel(score: number) {
    if (score >= 0.85) return t("testPanel.threshold.high");
    if (score >= 0.65) return t("testPanel.threshold.mid");
    return t("testPanel.threshold.low");
  }

  function scoreColor(score: number) {
    if (score >= 0.85) return "text-green-400";
    if (score >= 0.65) return "text-yellow-400";
    return "text-red-400";
  }

  return (
    <Card>
      <h3 className="text-sm font-semibold text-zinc-200 mb-3">
        🔍 {t("testPanel.title")}
      </h3>
      <div className="flex gap-2 mb-4">
        <Input
          placeholder={t("testPanel.queryPlaceholder")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleTest()}
          className="flex-1"
        />
        <Button onClick={handleTest} disabled={testing || !query.trim()}>
          {testing ? <Spinner size={14} /> : t("testPanel.test")}
        </Button>
      </div>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      {hits !== null && (
        <div className="space-y-2">
          {hits.length === 0 ? (
            <p className="text-sm text-zinc-500">{t("testPanel.noResults")}</p>
          ) : (
            hits.map((hit) => (
              <div
                key={hit.id}
                className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-3"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="text-sm font-medium text-zinc-200">
                    {hit.question}
                  </p>
                  <div className="shrink-0 text-right">
                    <span
                      className={`text-sm font-semibold ${scoreColor(hit.score)}`}
                    >
                      {Math.round(hit.score * 100)}%
                    </span>
                  </div>
                </div>
                <p className="text-xs text-zinc-400 mb-1.5 line-clamp-2">
                  {hit.answer}
                </p>
                <p className={`text-xs ${scoreColor(hit.score)}`}>
                  {scoreLabel(hit.score)}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </Card>
  );
}

// ─── FAQ Row ─────────────────────────────────────────────────────────────────
function FAQRow({
  faq,
  onEdit,
  onDelete,
}: {
  faq: FAQ;
  onEdit: (faq: FAQ) => void;
  onDelete: (id: string) => void;
}) {
  const tc = useTranslations("common");
  return (
    <div className="flex items-start gap-3 p-4 rounded-xl border border-zinc-800 bg-zinc-900/60 group hover:border-zinc-700 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm font-medium text-zinc-100 truncate">
            {faq.question}
          </p>
          {faq.category && (
            <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-violet-900/40 text-violet-400">
              {faq.category}
            </span>
          )}
          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 uppercase">
            {faq.language}
          </span>
        </div>
        <p className="text-xs text-zinc-500 line-clamp-2">{faq.answer}</p>
      </div>
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <Button variant="ghost" onClick={() => onEdit(faq)} className="px-2 py-1 text-xs">
          {tc("edit")}
        </Button>
        <Button
          variant="ghost"
          onClick={() => onDelete(faq.id)}
          className="px-2 py-1 text-xs text-red-400 hover:text-red-300"
        >
          {tc("delete")}
        </Button>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function KnowledgeBaseClient() {
  const t = useTranslations("knowledgeBase");
  const tc = useTranslations("common");
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [langFilter, setLangFilter] = useState<"all" | "uz" | "ru">("all");
  const [editingFaq, setEditingFaq] = useState<FAQ | null | "new">(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadFaqs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/faqs");
      if (res.ok) setFaqs(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFaqs();
  }, [loadFaqs]);

  async function handleDelete(id: string) {
    if (!confirm(t("deleteConfirm"))) return;
    await fetch(`/api/proxy/faqs/${id}`, { method: "DELETE" });
    setFaqs((prev) => prev.filter((f) => f.id !== id));
  }

  function handleSaved(saved: FAQ) {
    setFaqs((prev) => {
      const idx = prev.findIndex((f) => f.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setEditingFaq(null);
  }

  async function handleCSVImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const lines = text.split("\n").filter(Boolean);
    const [header, ...rows] = lines;
    const cols = header.split(",").map((c) => c.trim().toLowerCase());
    const qi = cols.indexOf("question");
    const ai = cols.indexOf("answer");
    const ci = cols.indexOf("category");
    const li = cols.indexOf("language");
    if (qi < 0 || ai < 0) return;

    for (const row of rows) {
      const parts = row.split(",");
      const body = {
        question: parts[qi]?.trim(),
        answer: parts[ai]?.trim(),
        category: ci >= 0 ? parts[ci]?.trim() || null : null,
        language: li >= 0 ? parts[li]?.trim() || "uz" : "uz",
      };
      if (!body.question || !body.answer) continue;
      const res = await fetch("/api/proxy/faqs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const saved = await res.json();
        setFaqs((prev) => [saved, ...prev]);
      }
    }
    e.target.value = "";
  }

  const filtered = faqs.filter((f) => {
    const matchLang = langFilter === "all" || f.language === langFilter;
    const matchSearch =
      !search ||
      f.question.toLowerCase().includes(search.toLowerCase()) ||
      f.answer.toLowerCase().includes(search.toLowerCase());
    return matchLang && matchSearch;
  });

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      {/* Left: FAQ list */}
      <div className="xl:col-span-2 space-y-4">
        {/* Toolbar */}
        <div className="flex flex-wrap gap-2 items-center">
          <Input
            placeholder={t("search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-48"
          />
          <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
            {(["all", "uz", "ru"] as const).map((lang) => (
              <button
                key={lang}
                onClick={() => setLangFilter(lang)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  langFilter === lang
                    ? "bg-violet-600 text-white"
                    : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                {t(
                  lang === "all"
                    ? "filterAll"
                    : lang === "uz"
                      ? "filterUz"
                      : "filterRu"
                )}
              </button>
            ))}
          </div>
          <Button
            variant="secondary"
            onClick={() => fileRef.current?.click()}
            className="text-xs"
          >
            📄 {t("importCsv")}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleCSVImport}
          />
          <Button onClick={() => setEditingFaq("new")}>
            + {t("addFaq")}
          </Button>
        </div>

        {/* List */}
        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        ) : filtered.length === 0 ? (
          <Card className="flex flex-col items-center py-16 text-center">
            <div className="text-4xl mb-3">📚</div>
            <p className="text-zinc-300 font-medium">
              {search || langFilter !== "all" ? t("noResults") : t("noFaqs")}
            </p>
            {!search && langFilter === "all" && (
              <p className="text-zinc-500 text-sm mt-1">{t("noFaqsHint")}</p>
            )}
          </Card>
        ) : (
          <div className="space-y-2">
            {filtered.map((faq) => (
              <FAQRow
                key={faq.id}
                faq={faq}
                onEdit={setEditingFaq}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* Right: RAG Test */}
      <div>
        <RAGTestPanel />
      </div>

      {/* Modal */}
      {editingFaq !== null && (
        <FAQModal
          faq={editingFaq === "new" ? null : editingFaq}
          onClose={() => setEditingFaq(null)}
          onSave={handleSaved}
        />
      )}
    </div>
  );
}
