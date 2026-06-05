"use client";

interface Props {
  metrics: {
    signals_today: number;
    runs_today: number;
    active_targets: number;
  };
}

export function MetricsBar({ metrics }: Props) {
  const stats = [
    { label: "Active targets", value: metrics.active_targets },
    { label: "Signals today", value: metrics.signals_today },
    { label: "Runs today", value: metrics.runs_today },
  ];

  return (
    <div className="flex items-center gap-8 pb-6 border-b border-white/[0.06]">
      {stats.map((s, i) => (
        <div key={s.label} className="flex items-baseline gap-2.5">
          <span className="text-2xl font-semibold tracking-tight text-white">{s.value}</span>
          <span className="text-sm text-white/30">{s.label}</span>
          {i < stats.length - 1 && <span className="ml-6 text-white/10">|</span>}
        </div>
      ))}
    </div>
  );
}
