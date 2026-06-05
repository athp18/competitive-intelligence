"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";

export function QueryBox() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ answer: string; iterations: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    setCollapsed(false);
    try {
      const res = await api.query(query);
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask anything — e.g. What happened with Rivian this week?"
          className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-4 py-2.5 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 transition-colors"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-brand text-white rounded-lg px-5 py-2.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-40 transition-colors shrink-0"
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      {error && (
        <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          {error}
        </div>
      )}

      {result && (
        <div className="border border-white/[0.06] rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.04]">
            <span className="text-xs text-white/20">{result.iterations} iterations</span>
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="text-xs text-white/20 hover:text-white/50 transition-colors"
            >
              {collapsed ? "expand" : "minimize"}
            </button>
          </div>
          {!collapsed && (
            <div className="p-4 text-sm text-white/70 leading-relaxed prose prose-invert prose-sm max-w-none
              prose-headings:text-white prose-headings:font-semibold
              prose-h3:text-sm prose-h3:mt-3 prose-h3:mb-1
              prose-p:text-white/70 prose-p:my-1
              prose-strong:text-white/90
              prose-ul:my-1 prose-li:my-0.5 prose-li:text-white/70
              prose-ol:my-1
              prose-hr:border-white/10">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
