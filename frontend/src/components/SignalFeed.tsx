"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";

interface Signal {
  id: string;
  signal_type: string;
  summary: string;
  relevance: string;
  source: string;
  signal_date: string | null;
  raw_url: string | null;
}

interface Target {
  id: string;
  name: string;
}

const TYPE_BADGE: Record<string, string> = {
  hiring: "text-emerald-400 bg-emerald-400/10",
  research: "text-blue-400 bg-blue-400/10",
  product: "text-violet-400 bg-violet-400/10",
  funding: "text-amber-400 bg-amber-400/10",
  mention: "text-white/30 bg-white/5",
};

const RELEVANCE_DOT: Record<string, string> = {
  high: "bg-red-400",
  medium: "bg-amber-400",
  low: "bg-white/20",
};

const STATUS_COLOR: Record<string, string> = {
  done: "text-emerald-400",
  running: "text-blue-400",
  failed: "text-red-400",
  pending: "text-amber-400",
};

const proseClass = `text-sm text-white/70 leading-relaxed prose prose-invert prose-sm max-w-none
  prose-headings:text-white prose-headings:font-semibold
  prose-h1:text-xl prose-h1:mt-0 prose-h1:mb-2
  prose-h2:text-lg prose-h2:mt-0 prose-h2:mb-2
  prose-h3:text-base prose-h3:mt-3 prose-h3:mb-1
  prose-p:text-white/70 prose-p:my-1
  prose-strong:text-white/90
  prose-ul:my-1 prose-li:my-0.5 prose-li:text-white/70
  prose-ol:my-1`;

interface Props {
  targetId: string;
  allTargets: Target[];
}

export function SignalFeed({ targetId, allTargets }: Props) {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [reports, setReports] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [runsOpen, setRunsOpen] = useState(false);
  const [compareTarget, setCompareTarget] = useState("");
  const [comparing, setComparing] = useState(false);
  const [compareResult, setCompareResult] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setRunsOpen(false);
    setCompareResult(null);
    Promise.all([
      api.getSignals(targetId, filter !== "all" ? { signal_type: filter } : undefined),
      api.getReports(targetId),
      api.listRuns({ target_id: targetId, limit: "8" }),
    ])
      .then(([sigs, reps, rs]) => {
        setSignals(sigs);
        setReports(reps);
        setRuns(rs);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [targetId, filter]);

  const latestDigest = reports.find((r) => r.report_type === "weekly_digest");
  const latestComparison = compareResult
    ? null
    : reports.find((r) => r.report_type === "comparison");

  async function triggerCompare() {
    if (!compareTarget) return;
    setComparing(true);
    setCompareResult(null);
    try {
      await api.compareTargets(targetId, compareTarget);
      // Poll for the comparison report
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        const reps = await api.getReports(targetId);
        const comp = reps.find((r: any) => r.report_type === "comparison");
        if (comp) {
          setCompareResult(comp.content);
          setReports(reps);
          clearInterval(poll);
          setComparing(false);
        } else if (attempts >= 15) {
          clearInterval(poll);
          setComparing(false);
          setCompareResult("Comparison is taking longer than expected. Check back shortly.");
        }
      }, 2000);
    } catch (err) {
      console.error(err);
      setComparing(false);
    }
  }

  const otherTargets = (allTargets ?? []).filter((t) => t.id !== targetId);

  return (
    <div className="space-y-5">
      {/* Weekly digest */}
      {latestDigest && (
        <div className="border border-white/[0.06] rounded-lg p-4">
          <p className="text-xs text-white/30 mb-2">
            Weekly digest &middot; {new Date(latestDigest.created_at).toLocaleDateString()}
          </p>
          <div className={proseClass}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{latestDigest.content}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Run history */}
      <div>
        <button
          onClick={() => setRunsOpen((o) => !o)}
          className="text-xs text-white/20 hover:text-white/40 transition-colors"
        >
          {runsOpen ? "Hide" : "Show"} recent runs {runs.length > 0 && `(${runs.length})`}
        </button>
        {runsOpen && (
          <div className="mt-2 border border-white/[0.06] rounded-lg overflow-hidden">
            {runs.length === 0 ? (
              <p className="text-xs text-white/20 p-3">No runs yet.</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/[0.06] text-white/20">
                    <th className="text-left px-3 py-2 font-normal">Source</th>
                    <th className="text-left px-3 py-2 font-normal">Status</th>
                    <th className="text-left px-3 py-2 font-normal">New signals</th>
                    <th className="text-left px-3 py-2 font-normal">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className="border-b border-white/[0.03] last:border-0">
                      <td className="px-3 py-2 text-white/50">{r.source}</td>
                      <td className={`px-3 py-2 ${STATUS_COLOR[r.status] || "text-white/30"}`}>
                        {r.status}
                      </td>
                      <td className="px-3 py-2 text-white/30">
                        {r.signals_new != null ? `+${r.signals_new}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-white/20">
                        {r.started_at ? new Date(r.started_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Signal type filter */}
      <div className="flex items-center gap-1.5">
        {["all", "hiring", "research", "product", "funding", "mention"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-2.5 py-1 rounded transition-colors ${
              filter === f ? "bg-white/10 text-white" : "text-white/30 hover:text-white/50"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Signals */}
      {loading ? (
        <div className="text-white/20 text-sm py-8 text-center">Loading...</div>
      ) : signals.length === 0 ? (
        <div className="text-white/20 text-sm py-12 text-center">
          No signals yet. Trigger a crawl to fetch data.
        </div>
      ) : (
        <div className="space-y-px">
          {signals.map((s) => (
            <SignalRow key={s.id} signal={s} />
          ))}
        </div>
      )}

      {/* Comparison */}
      {otherTargets.length > 0 && (
        <div className="border border-white/[0.06] rounded-lg p-4 space-y-3">
          <p className="text-xs text-white/30">Compare with</p>
          <div className="flex gap-2">
            <select
              value={compareTarget}
              onChange={(e) => setCompareTarget(e.target.value)}
              className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-white/20 transition-colors bg-[#0a0a0a]"
            >
              <option value="">Select a target...</option>
              {otherTargets.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <button
              onClick={triggerCompare}
              disabled={!compareTarget || comparing}
              className="text-xs bg-brand text-white rounded px-4 py-2 hover:bg-indigo-500 disabled:opacity-40 transition-colors shrink-0"
            >
              {comparing ? "Generating..." : "Compare"}
            </button>
          </div>
          {(compareResult || latestComparison) && (
            <div className={proseClass}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {compareResult || latestComparison?.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  return (
    <div className="py-3.5 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors px-1 group">
      <div className="flex items-start gap-3">
        <div className="flex items-center gap-2 pt-0.5 shrink-0">
          <span
            className={`text-[11px] px-1.5 py-0.5 rounded font-medium ${
              TYPE_BADGE[signal.signal_type] || "text-white/20 bg-white/5"
            }`}
          >
            {signal.signal_type}
          </span>
          <div
            className={`w-1 h-1 rounded-full ${RELEVANCE_DOT[signal.relevance] || "bg-white/20"}`}
            title={signal.relevance}
          />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-white/80 leading-relaxed">{signal.summary}</p>
          <div className="flex items-center gap-3 mt-1.5">
            <span className="text-xs text-white/20">{signal.source}</span>
            {signal.signal_date && (
              <span className="text-xs text-white/20">{signal.signal_date}</span>
            )}
            {signal.raw_url && (
              <a
                href={signal.raw_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-white/20 hover:text-white/50 transition-colors truncate max-w-xs"
              >
                {(() => { try { return new URL(signal.raw_url).hostname; } catch { return signal.raw_url; } })()}
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
