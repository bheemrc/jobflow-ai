"use client";

import type { TokenUsageSummary } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface TokenUsagePanelProps {
  usage: TokenUsageSummary | null;
}

export default function TokenUsagePanel({ usage }: TokenUsagePanelProps) {
  if (!usage) {
    return (
      <Card className="p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Token Usage</h3>
        <p className="text-xs text-muted-foreground/70">
          No usage data yet. Start a bot to begin tracking.
        </p>
      </Card>
    );
  }

  const botEntries = Object.entries(usage.by_bot);
  const maxCost = Math.max(...botEntries.map(([, v]) => v.cost), 0.001);

  // Cost projection: avg daily cost from last 7 days -> monthly estimate
  const dailyCosts = usage.daily.slice(-7).map((d) => d.cost);
  const avgDailyCost = dailyCosts.length > 0
    ? dailyCosts.reduce((a, b) => a + b, 0) / dailyCosts.length
    : 0;
  const monthlyProjection = avgDailyCost * 30;

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Token Usage</h3>
        <span className="data-mono text-lg font-bold text-primary">
          ${usage.total_cost.toFixed(4)}
        </span>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="rounded-lg p-2.5 bg-card border">
          <p className="text-[9px] uppercase tracking-wider mb-1 text-muted-foreground/70">
            Total Runs
          </p>
          <p className="data-mono text-base font-semibold text-foreground">
            {usage.total_runs}
          </p>
        </div>
        <div className="rounded-lg p-2.5 bg-card border">
          <p className="text-[9px] uppercase tracking-wider mb-1 text-muted-foreground/70">
            Tokens Used
          </p>
          <p className="data-mono text-base font-semibold text-foreground">
            {((usage.total_input_tokens + usage.total_output_tokens) / 1000).toFixed(1)}k
          </p>
        </div>
      </div>

      {/* Cost projection */}
      {avgDailyCost > 0 && (
        <div className="rounded-lg p-2.5 mb-4 bg-primary/10 border border-primary/20">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium text-muted-foreground">
              Monthly projection
            </p>
            <p className="data-mono text-sm font-bold text-primary">
              ~${monthlyProjection.toFixed(2)}/mo
            </p>
          </div>
          <p className="text-[9px] mt-0.5 text-muted-foreground/70">
            Based on ${avgDailyCost.toFixed(4)}/day avg over last {dailyCosts.length} days
          </p>
        </div>
      )}

      {/* Per-bot breakdown */}
      {botEntries.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 text-muted-foreground/70">
            Cost by Bot
          </p>
          <div className="space-y-2">
            {botEntries
              .sort(([, a], [, b]) => b.cost - a.cost)
              .map(([name, data]) => (
                <div key={name}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      {name.replace(/_/g, " ")}
                    </span>
                    <span className="data-mono text-[11px] text-muted-foreground/70">
                      ${data.cost.toFixed(4)}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden bg-muted">
                    <div
                      className="h-full rounded-full transition-all duration-500 bg-primary/80"
                      style={{
                        width: `${Math.max(2, (data.cost / maxCost) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Daily sparkline */}
      {usage.daily.length > 0 && (
        <div className="mt-4 pt-3 border-t">
          <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 text-muted-foreground/70">
            Daily Cost (last 7 days)
          </p>
          <div className="flex items-end gap-1 h-10">
            {usage.daily.slice(-7).reverse().map((d, i) => {
              const maxDaily = Math.max(...usage.daily.map((x) => x.cost), 0.001);
              const h = Math.max(4, (d.cost / maxDaily) * 40);
              return (
                <div
                  key={i}
                  className="flex-1 rounded-sm transition-all bg-primary"
                  style={{
                    height: h,
                    opacity: 0.6 + (i / 7) * 0.4,
                  }}
                  title={`${d.date}: $${d.cost.toFixed(4)}`}
                />
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}
