"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Target {
  id: string;
  name: string;
  type: string;
  active: boolean;
  sources: Record<string, any>;
}

interface Props {
  target: Target;
  selected: boolean;
  onClick: () => void;
  onUpdated: (t: Target) => void;
  onDeleted: (id: string) => void;
}

const TYPE_COLORS: Record<string, string> = {
  company: "text-emerald-400",
  person: "text-blue-400",
  topic: "text-amber-400",
  repo: "text-purple-400",
};

const inputClass =
  "w-full bg-white/[0.04] border border-white/[0.08] rounded px-3 py-1.5 text-xs text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 transition-colors";

export function TargetCard({ target, selected, onClick, onUpdated, onDeleted }: Props) {
  const [triggering, setTriggering] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Edit form state — derived from current sources
  const [name, setName] = useState(target.name);
  const [query, setQuery] = useState(target.sources.hn?.query || target.sources.news?.query || "");
  const [ghOrg, setGhOrg] = useState(target.sources.github?.org || "");
  const [domain, setDomain] = useState(target.sources.careers?.domain || "");
  const [jobSlug, setJobSlug] = useState(target.sources.greenhouse?.slug || target.sources.lever?.slug || "");

  async function triggerCrawl(e: React.MouseEvent) {
    e.stopPropagation();
    setTriggering(true);
    try {
      await api.triggerRun(target.id);
      setTriggered(true);
      setTimeout(() => setTriggered(false), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setTriggering(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const sources: Record<string, object> = {};
      if (query) {
        sources.hn = { query, include_hiring: true };
        sources.news = { query };
        sources.googlenews = { query };
      }
      if (ghOrg) sources.github = { org: ghOrg };
      if (domain) sources.careers = { domain };
      if (jobSlug) {
        sources.greenhouse = { slug: jobSlug };
        sources.lever = { slug: jobSlug };
      }
      const updated = await api.updateTarget(target.id, { name, sources });
      onUpdated(updated);
      setEditing(false);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  async function deleteTarget(e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm(`Remove "${target.name}"?`)) return;
    try {
      await api.deleteTarget(target.id);
      onDeleted(target.id);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div
      onClick={() => { if (!editing) onClick(); }}
      className={`rounded-lg px-4 py-3 transition-all ${editing ? "bg-white/[0.06]" : "cursor-pointer"} ${
        selected && !editing ? "bg-white/[0.06] text-white" : "hover:bg-white/[0.03] text-white/60"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${selected ? "bg-brand" : "bg-white/20"}`} />
          <p className="text-sm font-medium truncate">{target.name}</p>
          <span className={`text-xs shrink-0 ${TYPE_COLORS[target.type] || "text-white/20"}`}>
            {target.type}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); setEditing((v) => !v); }}
            className="text-xs text-white/20 hover:text-white/50 transition-colors px-1"
          >
            {editing ? "cancel" : "edit"}
          </button>
          <button
            onClick={triggerCrawl}
            disabled={triggering}
            className={`text-xs px-2 py-0.5 rounded border transition-colors disabled:opacity-30 ${
              triggered
                ? "border-emerald-500/30 text-emerald-400"
                : "border-white/10 text-white/30 hover:border-white/20 hover:text-white/60"
            }`}
          >
            {triggering ? "queuing..." : triggered ? "queued" : "Trigger crawl"}
          </button>
        </div>
      </div>

      {editing && (
        <form onSubmit={save} onClick={(e) => e.stopPropagation()} className="mt-3 space-y-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            className={inputClass}
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search query (news, HN, Google News)"
            className={inputClass}
          />
          <input
            value={ghOrg}
            onChange={(e) => setGhOrg(e.target.value)}
            placeholder="GitHub org (optional)"
            className={inputClass}
          />
          <input
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="Domain for careers page (e.g. rivian.com)"
            className={inputClass}
          />
          <input
            value={jobSlug}
            onChange={(e) => setJobSlug(e.target.value)}
            placeholder="Greenhouse / Lever slug (optional)"
            className={inputClass}
          />
          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              onClick={deleteTarget}
              className="text-xs text-red-400/60 hover:text-red-400 transition-colors"
            >
              Delete target
            </button>
            <button
              type="submit"
              disabled={saving}
              className="text-xs bg-brand text-white rounded px-3 py-1 hover:bg-indigo-500 disabled:opacity-40 transition-colors"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
