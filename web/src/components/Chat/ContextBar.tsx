import { useState } from 'react';

interface ContextUsage {
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  max_context_tokens: number;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/** Estimate USD cost from token counts (Opus 4 pricing). */
function estimateCost(u: ContextUsage): number {
  return (
    u.input_tokens * 15 / 1_000_000            // fresh input
    + u.cache_read_input_tokens * 1.5 / 1_000_000   // cache read (90% off)
    + u.cache_creation_input_tokens * 18.75 / 1_000_000  // cache write (25% premium)
    + u.output_tokens * 75 / 1_000_000          // output
  );
}

export function ContextBar({ usage, sessionCostUsd }: { usage: ContextUsage; sessionCostUsd?: number }) {
  const [hovering, setHovering] = useState(false);

  // SDK's input_tokens is only non-cached input; total context = all input + output
  const totalInput = usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens;
  const used = totalInput + usage.output_tokens;
  const max = usage.max_context_tokens;
  const pct = Math.min((used / max) * 100, 100);

  const turnCost = estimateCost(usage);
  const cacheRate = totalInput > 0
    ? (usage.cache_read_input_tokens / totalInput * 100)
    : 0;

  // Color based on usage level
  let barColor = '#3b82f6'; // blue
  if (pct > 80) barColor = '#ef4444'; // red
  else if (pct > 60) barColor = '#f59e0b'; // amber

  return (
    <div
      className="relative flex items-center gap-2 cursor-default"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <span className="text-[11px] text-text-dim whitespace-nowrap">
        {formatTokens(used)} / {formatTokens(max)}
      </span>
      <div className="w-20 h-1.5 bg-border-subtle rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>

      {hovering && (
        <div className="absolute right-0 top-full mt-2 z-50 bg-surface-raised border border-border-subtle rounded-lg p-3 shadow-xl min-w-[220px]">
          <div className="text-[11px] text-text-muted uppercase tracking-wider mb-2">Context Usage</div>
          <div className="space-y-1.5 text-[12px]">
            <Row label="Fresh input" value={usage.input_tokens} />
            <Row label="Output tokens" value={usage.output_tokens} />
            {usage.cache_read_input_tokens > 0 && (
              <Row label="Cache read" value={usage.cache_read_input_tokens} color="#22c55e" />
            )}
            {usage.cache_creation_input_tokens > 0 && (
              <Row label="Cache created" value={usage.cache_creation_input_tokens} color="#a855f7" />
            )}
            <div className="border-t border-border-subtle my-1.5" />
            <Row label="Total used" value={used} bold />
            <Row label="Max context" value={max} />
            <Row label="Remaining" value={max - used} color={pct > 80 ? '#ef4444' : '#22c55e'} />

            {/* Cost section */}
            <div className="border-t border-border-subtle my-1.5" />
            <div className="text-[11px] text-text-muted uppercase tracking-wider mb-1">Cost</div>
            <CostRow label="This turn" value={turnCost} />
            {(sessionCostUsd ?? 0) > 0 && (
              <CostRow label="Session total" value={sessionCostUsd!} bold />
            )}
            {cacheRate > 0 && (
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Cache hit rate</span>
                <span className="text-text-muted" style={{ color: cacheRate > 50 ? '#22c55e' : undefined }}>
                  {cacheRate.toFixed(1)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, color, bold }: { label: string; value: number; color?: string; bold?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-text-muted">{label}</span>
      <span className={bold ? 'text-text font-medium' : 'text-text-muted'} style={color ? { color } : undefined}>
        {formatTokens(value)}
      </span>
    </div>
  );
}

function CostRow({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  const formatted = value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
  return (
    <div className="flex justify-between items-center">
      <span className="text-text-muted">{label}</span>
      <span className={bold ? 'text-text font-medium' : 'text-text-muted'}>
        {formatted}
      </span>
    </div>
  );
}
