"use client";

import { useEffect, useState } from "react";
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

interface Props {
  targetId: string;
}

export function SignalFeed({ targetId }: Props) {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [reports, setReports] = useState<any[]>([]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getSignals(targetId, filter !== "all" ? { signal_type: filter } : undefined),
      api.getReports(targetId),
    ])
      .then(([sigs, reps]) => {
        setSignals(sigs);
        setReports(reps);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [targetId, filter]);

  const latestDigest = reports.find((r) => r.report_type === "weekly_digest");

  return (
    <div className="space-y-5">
      {latestDigest && (
        <div className="border border-white/[0.06] rounded-lg p-4">
          <p className="text-xs text-white/30 mb-2">Weekly digest &middot; {new Date(latestDigest.created_at).toLocaleDateString()}</p>
          <p className="text-sm text-white/70 leading-relaxed">{latestDigest.content}</p>
        </div>
      )}

      <div className="flex items-center gap-1.5">
        {["all", "hiring", "research", "product", "funding", "mention"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-2.5 py-1 rounded transition-colors ${
              filter === f
                ? "bg-white/10 text-white"
                : "text-white/30 hover:text-white/50"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

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
                {new URL(signal.raw_url).hostname}
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
