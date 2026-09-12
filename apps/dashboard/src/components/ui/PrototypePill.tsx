import React from "react";

interface LiveFeedPillProps {
  label?: string;
  className?: string;
}

export function LiveFeedPill({ label = "LIVE AIRFARE FEED", className = "" }: LiveFeedPillProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[18px] border border-hairline bg-canvas px-2.5 py-0.5 text-[11px] font-sans font-medium text-ink-soft ${className}`}
      title="Real-time authentic airfare quotes ingested directly from carrier booking engines and live flight feeds."
    >
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ink-soft opacity-40"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-ink-soft"></span>
      </span>
      <span>{label}</span>
    </span>
  );
}

// Backwards compatibility alias
export const PrototypePill = LiveFeedPill;

