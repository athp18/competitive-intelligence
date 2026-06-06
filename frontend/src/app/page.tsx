"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { QueryBox } from "@/components/QueryBox";
import { MetricsBar } from "@/components/MetricsBar";
import { TargetCard } from "@/components/TargetCard";
import { SignalFeed } from "@/components/SignalFeed";

export default function Home() {
  const [targets, setTargets] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listTargets(), api.getMetrics()])
      .then(([t, m]) => {
        setTargets(t);
        setMetrics(m);
        if (t.length > 0) setSelectedTarget(t[0].id);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-7">
      {metrics && <MetricsBar metrics={metrics} />}

      <QueryBox />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-1">
          <p className="text-xs text-white/20 mb-2 px-1">Targets</p>
          <div className="-mx-1">
            {targets.length === 0 ? (
              <p className="text-white/20 text-sm px-1">No targets yet.</p>
            ) : (
              targets.map((t) => (
                <TargetCard
                  key={t.id}
                  target={t}
                  selected={selectedTarget === t.id}
                  onClick={() => setSelectedTarget(t.id)}
                  onUpdated={(updated) =>
                    setTargets((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
                  }
                  onDeleted={(id) => {
                    setTargets((prev) => prev.filter((x) => x.id !== id));
                    if (selectedTarget === id) setSelectedTarget(targets.find((x) => x.id !== id)?.id ?? null);
                  }}
                />
              ))
            )}
          </div>
          <AddTargetForm onAdded={(t) => setTargets((prev) => [...prev, t])} />
        </div>

        <div className="lg:col-span-3">
          {selectedTarget ? (
            <SignalFeed targetId={selectedTarget} allTargets={targets} />
          ) : (
            <div className="text-white/20 text-sm py-12 text-center">
              Select a target to view signals.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AddTargetForm({ onAdded }: { onAdded: (t: any) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("company");
  const [ghOrg, setGhOrg] = useState("");
  const [jobSlug, setJobSlug] = useState("");
  const [domain, setDomain] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const sources: Record<string, object> = {
        hn: { query: name, include_hiring: true },
        news: { query: name },
        googlenews: { query: name },
      };
      if (ghOrg) sources.github = { org: ghOrg };
      if (jobSlug) {
        sources.greenhouse = { slug: jobSlug };
        sources.lever = { slug: jobSlug };
      }
      if (domain) sources.careers = { domain };

      const schedule: Record<string, string> = { hn: "6h", news: "6h", googlenews: "6h" };
      if (ghOrg) schedule.github = "daily";
      if (jobSlug) { schedule.greenhouse = "daily"; schedule.lever = "daily"; }
      if (domain) schedule.careers = "daily";

      const target = await api.createTarget({ name, type, sources, schedule, aliases: [] });
      onAdded(target);
      setOpen(false);
      setName("");
    } catch (err) {
      alert("Failed to create target: " + err);
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full text-xs text-white/20 hover:text-white/40 py-2 px-1 text-left transition-colors mt-1"
      >
        + Add target
      </button>
    );
  }

  const inputClass = "w-full bg-white/[0.04] border border-white/[0.08] rounded px-3 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 transition-colors";

  return (
    <form onSubmit={submit} className="border border-white/[0.08] rounded-lg p-4 space-y-2.5 mt-2">
      <p className="text-xs text-white/30 mb-3">New target</p>
      <input
        required
        placeholder="Company name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className={inputClass}
      />
      <select
        value={type}
        onChange={(e) => setType(e.target.value)}
        className={`${inputClass} bg-[#0a0a0a]`}
      >
        <option value="company">Company</option>
        <option value="person">Person</option>
        <option value="topic">Topic</option>
        <option value="repo">Repository</option>
      </select>
      <input
        placeholder="GitHub org (optional)"
        value={ghOrg}
        onChange={(e) => setGhOrg(e.target.value)}
        className={inputClass}
      />
      <input
        placeholder="Domain for careers page (e.g. rivian.com)"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        className={inputClass}
      />
      <input
        placeholder="Greenhouse / Lever slug (optional)"
        value={jobSlug}
        onChange={(e) => setJobSlug(e.target.value)}
        className={inputClass}
      />
      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={submitting}
          className="flex-1 bg-brand text-white rounded py-2 text-xs font-medium hover:bg-indigo-500 disabled:opacity-40 transition-colors"
        >
          {submitting ? "Adding..." : "Add"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="flex-1 text-white/30 hover:text-white/50 rounded py-2 text-xs transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
