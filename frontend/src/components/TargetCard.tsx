"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Target {
  id: string;
  name: string;
  type: string;
  active: boolean;
  sources: Record<string, object>;
}

interface Props {
  target: Target;
  selected: boolean;
  onClick: () => void;
}

const TYPE_COLORS: Record<string, string> = {
  company: "text-emerald-400",
  person: "text-blue-400",
  topic: "text-amber-400",
  repo: "text-purple-400",
};

export function TargetCard({ target, selected, onClick }: Props) {
  const [triggering, setTriggering] = useState(false);
  const [triggered, setTriggered] = useState(false);

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

  return (
    <div
      onClick={onClick}
      className={`cursor-pointer rounded-lg px-4 py-3 transition-all group ${
        selected ? "bg-white/[0.06] text-white" : "hover:bg-white/[0.03] text-white/60"
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
        <button
          onClick={triggerCrawl}
          disabled={triggering}
          className={`text-xs shrink-0 px-2 py-0.5 rounded border transition-colors disabled:opacity-30 ${
            triggered
              ? "border-emerald-500/30 text-emerald-400"
              : "border-white/10 text-white/30 hover:border-white/20 hover:text-white/60"
          }`}
        >
          {triggering ? "queuing..." : triggered ? "queued" : "Trigger crawl"}
        </button>
      </div>
    </div>
  );
}
