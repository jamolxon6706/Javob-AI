"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Input, Spinner } from "@javobai/ui";
import { apiClient } from "@/lib/api-client";

// ─── Types (mirrors apps/api/src/javobai/analytics/schemas.py) ────────────

interface SourceBreakdown {
  faq: number;
  llm: number;
  action: number;
  flow: number;
  handoff: number;
  operator: number;
}

interface ChannelVolume {
  platform: string;
  inbound: number;
  outbound: number;
}

interface Overview {
  days: number;
  total_conversations: number;
  total_messages: number;
  inbound_messages: number;
  outbound_messages: number;
  reply_rate: number;
  handoff_rate: number;
  avg_response_time_ms: number | null;
  angry_count: number;
  by_source: SourceBreakdown;
  by_channel: ChannelVolume[];
  by_handoff_reason: Record<string, number>;
}

interface TimeseriesPoint {
  date: string;
  inbound: number;
  outbound: number;
  handoff: number;
}

interface TopQuestion {
  text: string;
  count: number;
}

interface TopQuestionsOut {
  top_questions: TopQuestion[];
  faq_gaps: TopQuestion[];
}

interface EvalCase {
  id: string;
  question: string;
  language: string;
  expected_faq_id: string | null;
  expected_answer_contains: string | null;
  is_active: boolean;
}

interface EvalResult {
  eval_case_id: string;
  question: string;
  passed: boolean;
  actual_source: string | null;
  actual_faq_id: string | null;
  actual_score: number | null;
  actual_answer: string | null;
}

interface EvalRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  total: number;
  passed: number;
  failed: number;
  is_regression: boolean;
}

interface EvalQuality {
  case_count: number;
  latest_run: EvalRun | null;
  latest_run_results: EvalResult[];
  history: EvalRun[];
}

const SOURCE_COLORS: Record<string, string> = {
  faq: "#22c55e",
  llm: "#8b5cf6",
  action: "#0ea5e9",
  flow: "#f59e0b",
  handoff: "#ef4444",
  operator: "#a1a1aa",
};

function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="text-2xl font-semibold text-white mt-1">{value}</p>
      {hint && <p className="text-xs text-zinc-500 mt-1">{hint}</p>}
    </Card>
  );
}

function TimeseriesChart({ points }: { points: TimeseriesPoint[] }) {
  if (points.length === 0) return null;
  const width = 640;
  const height = 180;
  const padding = 24;
  const maxVal = Math.max(1, ...points.map((p) => Math.max(p.inbound, p.outbound)));
  const stepX = (width - padding * 2) / Math.max(1, points.length - 1);
  const y = (v: number) => height - padding - (v / maxVal) * (height - padding * 2);
  const x = (i: number) => padding + i * stepX;

  const line = (key: "inbound" | "outbound") =>
    points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-44">
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#3f3f46" />
      <path d={line("inbound")} fill="none" stroke="#0ea5e9" strokeWidth={2} />
      <path d={line("outbound")} fill="none" stroke="#8b5cf6" strokeWidth={2} />
      {points.map((p, i) =>
        p.handoff > 0 ? (
          <circle key={p.date} cx={x(i)} cy={y(p.outbound)} r={3} fill="#ef4444" />
        ) : null
      )}
    </svg>
  );
}

function SourceBars({ bySource }: { bySource: SourceBreakdown }) {
  const total = Object.values(bySource).reduce((a, b) => a + b, 0);
  if (total === 0) return null;
  return (
    <div className="space-y-2">
      {(Object.keys(bySource) as (keyof SourceBreakdown)[])
        .filter((k) => bySource[k] > 0)
        .sort((a, b) => bySource[b] - bySource[a])
        .map((key) => {
          const pct = Math.round((bySource[key] / total) * 100);
          return (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="w-16 shrink-0 capitalize text-zinc-400">{key}</span>
              <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, backgroundColor: SOURCE_COLORS[key] ?? "#71717a" }}
                />
              </div>
              <span className="w-14 text-right text-zinc-500">{bySource[key]} ({pct}%)</span>
            </div>
          );
        })}
    </div>
  );
}

function handoffReasonLabel(t: ReturnType<typeof useTranslations>, reason: string): string {
  const known = ["low_confidence", "out_of_window", "rate_limited", "needs_template", "angry_customer"];
  return known.includes(reason) ? t(`handoffReason.${reason}` as never) : reason;
}

type Tab = "overview" | "questions" | "quality";

export function AnalyticsClient() {
  const t = useTranslations("analytics");
  const [tab, setTab] = useState<Tab>("overview");
  const [days, setDays] = useState(7);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [overviewLoading, setOverviewLoading] = useState(true);

  const [questions, setQuestions] = useState<TopQuestionsOut | null>(null);
  const [questionsLoading, setQuestionsLoading] = useState(false);

  const [quality, setQuality] = useState<EvalQuality | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [newContains, setNewContains] = useState("");
  const [savingCase, setSavingCase] = useState(false);
  const [runningEval, setRunningEval] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    try {
      const [ov, ts] = await Promise.all([
        apiClient.get<Overview>(`/analytics/overview?days=${days}`),
        apiClient.get<{ points: TimeseriesPoint[] }>(`/analytics/timeseries?days=${days}`),
      ]);
      setOverview(ov.data ?? null);
      setTimeseries(ts.data?.points ?? []);
    } finally {
      setOverviewLoading(false);
    }
  }, [days]);

  const loadQuestions = useCallback(async () => {
    setQuestionsLoading(true);
    try {
      const res = await apiClient.get<TopQuestionsOut>(`/analytics/top-questions?days=${days}`);
      setQuestions(res.data ?? null);
    } finally {
      setQuestionsLoading(false);
    }
  }, [days]);

  const loadQuality = useCallback(async () => {
    setQualityLoading(true);
    try {
      const [qRes, cRes] = await Promise.all([
        apiClient.get<EvalQuality>("/analytics/quality"),
        apiClient.get<EvalCase[]>("/analytics/eval-cases"),
      ]);
      setQuality(qRes.data ?? null);
      setCases(cRes.data ?? []);
    } finally {
      setQualityLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    if (tab === "questions") loadQuestions();
    if (tab === "quality") loadQuality();
  }, [tab, loadQuestions, loadQuality]);

  const handleAddCase = async () => {
    if (!newQuestion.trim() || !newContains.trim()) return;
    setSavingCase(true);
    try {
      await apiClient.post("/analytics/eval-cases", {
        question: newQuestion,
        expected_answer_contains: newContains,
      });
      setNewQuestion("");
      setNewContains("");
      await loadQuality();
    } finally {
      setSavingCase(false);
    }
  };

  const handleDeleteCase = async (id: string) => {
    await apiClient.delete(`/analytics/eval-cases/${id}`);
    await loadQuality();
  };

  const handleRunEval = async () => {
    setRunningEval(true);
    setEvalError(null);
    try {
      await apiClient.post("/analytics/eval-cases/run");
      // The harness runs as a background ARQ job — give it a moment, then refresh.
      setTimeout(loadQuality, 1500);
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : t("evalRunFailed"));
    } finally {
      setRunningEval(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: t("tabOverview") },
    { key: "questions", label: t("tabQuestions") },
    { key: "quality", label: t("tabQuality") },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-zinc-800">
        <div className="flex gap-1">
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
        {tab !== "quality" && (
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="mb-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white px-3 py-1.5 text-sm"
          >
            <option value={7}>{t("last7Days")}</option>
            <option value={30}>{t("last30Days")}</option>
            <option value={90}>{t("last90Days")}</option>
          </select>
        )}
      </div>

      {/* ── Overview tab ── */}
      {tab === "overview" && (
        overviewLoading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : !overview || overview.total_messages === 0 ? (
          <Card className="p-8 text-center text-zinc-500">{t("noData")}</Card>
        ) : (
          <div className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard label={t("replyRate")} value={`${Math.round(overview.reply_rate * 100)}%`} />
              <KpiCard label={t("handoffRate")} value={`${Math.round(overview.handoff_rate * 100)}%`} />
              <KpiCard
                label={t("avgResponseTime")}
                value={overview.avg_response_time_ms != null ? `${Math.round(overview.avg_response_time_ms)} ms` : "—"}
              />
              <KpiCard
                label={t("angryCustomers")}
                value={String(overview.angry_count)}
                hint={overview.angry_count > 0 ? t("autoEscalated") : undefined}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="p-4">
                <p className="text-sm font-medium text-white mb-3">{t("volumeOverTime")}</p>
                <TimeseriesChart points={timeseries} />
                <div className="flex gap-4 text-xs text-zinc-500 mt-2">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sky-500" />{t("inbound")}</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-violet-500" />{t("outbound")}</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />{t("handoff")}</span>
                </div>
              </Card>

              <Card className="p-4">
                <p className="text-sm font-medium text-white mb-3">{t("answersBySource")}</p>
                <SourceBars bySource={overview.by_source} />
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="p-4">
                <p className="text-sm font-medium text-white mb-3">{t("byChannel")}</p>
                <div className="space-y-2">
                  {overview.by_channel.map((c) => (
                    <div key={c.platform} className="flex items-center justify-between text-sm">
                      <span className="capitalize text-zinc-300">{c.platform}</span>
                      <span className="text-zinc-500">
                        {c.inbound} {t("inbound").toLowerCase()} · {c.outbound} {t("outbound").toLowerCase()}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="p-4">
                <p className="text-sm font-medium text-white mb-3">{t("handoffReasons")}</p>
                {Object.keys(overview.by_handoff_reason).length === 0 ? (
                  <p className="text-sm text-zinc-500">{t("noHandoffs")}</p>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(overview.by_handoff_reason).map(([reason, count]) => (
                      <div key={reason} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-300">{handoffReasonLabel(t, reason)}</span>
                        <span className="text-zinc-500">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>
        )
      )}

      {/* ── Questions tab ── */}
      {tab === "questions" && (
        questionsLoading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-4">
              <p className="text-sm font-medium text-white mb-3">{t("topQuestions")}</p>
              {!questions || questions.top_questions.length === 0 ? (
                <p className="text-sm text-zinc-500">{t("noData")}</p>
              ) : (
                <ol className="space-y-2">
                  {questions.top_questions.map((q, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-zinc-300 truncate">{q.text}</span>
                      <span className="shrink-0 rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                        {q.count}×
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Card>

            <Card className="p-4">
              <p className="text-sm font-medium text-white mb-1">{t("faqGaps")}</p>
              <p className="text-xs text-zinc-500 mb-3">{t("faqGapsHint")}</p>
              {!questions || questions.faq_gaps.length === 0 ? (
                <p className="text-sm text-zinc-500">{t("noGaps")}</p>
              ) : (
                <ol className="space-y-2">
                  {questions.faq_gaps.map((q, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-zinc-300 truncate">{q.text}</span>
                      <span className="shrink-0 rounded-full bg-red-900/60 px-2 py-0.5 text-xs text-red-300">
                        {q.count}×
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>
        )
      )}

      {/* ── Quality (AI eval harness) tab ── */}
      {tab === "quality" && (
        qualityLoading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : (
          <div className="space-y-4">
            {quality?.latest_run?.is_regression && (
              <Card className="p-4 border-red-800 bg-red-950/40">
                <p className="text-sm font-medium text-red-300">{t("regressionDetected")}</p>
                <p className="text-xs text-red-400/80 mt-1">{t("regressionHint")}</p>
              </Card>
            )}

            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-white">{t("latestRun")}</p>
                <Button onClick={handleRunEval} disabled={runningEval || cases.filter((c) => c.is_active).length === 0}>
                  {runningEval ? <Spinner size={16} /> : t("runEval")}
                </Button>
              </div>
              {evalError && <p className="text-red-400 text-sm mb-2">{evalError}</p>}
              {!quality?.latest_run ? (
                <p className="text-sm text-zinc-500">{t("noRunsYet")}</p>
              ) : (
                <>
                  <div className="flex gap-4 text-sm mb-3">
                    <span className="text-green-400">{quality.latest_run.passed} {t("passed")}</span>
                    <span className="text-red-400">{quality.latest_run.failed} {t("failed")}</span>
                    <span className="text-zinc-500">{t("of")} {quality.latest_run.total}</span>
                  </div>
                  <div className="space-y-1">
                    {quality.latest_run_results.map((r) => (
                      <div key={r.eval_case_id} className="flex items-center gap-2 text-xs">
                        <span className={r.passed ? "text-green-400" : "text-red-400"}>
                          {r.passed ? "✓" : "✗"}
                        </span>
                        <span className="text-zinc-300 truncate flex-1">{r.question}</span>
                        <span className="text-zinc-500">{r.actual_source ?? "handoff"}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </Card>

            <Card className="p-4">
              <p className="text-sm font-medium text-white mb-3">{t("goldenTestSet")}</p>
              <div className="flex flex-col sm:flex-row gap-2 mb-4">
                <Input
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  placeholder={t("questionPlaceholder")}
                  className="flex-1"
                />
                <Input
                  value={newContains}
                  onChange={(e) => setNewContains(e.target.value)}
                  placeholder={t("expectedContainsPlaceholder")}
                  className="flex-1"
                />
                <Button onClick={handleAddCase} disabled={savingCase}>
                  {savingCase ? <Spinner size={16} /> : t("addCase")}
                </Button>
              </div>
              {cases.length === 0 ? (
                <p className="text-sm text-zinc-500">{t("noCases")}</p>
              ) : (
                <div className="space-y-2">
                  {cases.map((c) => (
                    <div key={c.id} className="flex items-center justify-between gap-2 text-sm border-t border-zinc-800 pt-2">
                      <div className="min-w-0">
                        <p className="text-zinc-200 truncate">{c.question}</p>
                        <p className="text-xs text-zinc-500 truncate">
                          {c.expected_faq_id ? `FAQ: ${c.expected_faq_id}` : `⊃ "${c.expected_answer_contains}"`}
                        </p>
                      </div>
                      <Button variant="ghost" onClick={() => handleDeleteCase(c.id)}>🗑</Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )
      )}
    </div>
  );
}
