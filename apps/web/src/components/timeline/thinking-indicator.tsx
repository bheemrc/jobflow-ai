"use client";

import { useEffect, useRef, memo, useCallback } from "react";
import type { AgentPersonality } from "@/lib/use-timeline-events";

interface ThinkingIndicatorProps {
  agents: string[];
  personalities: Record<string, AgentPersonality>;
}

const THINKING_PHASES = [
  { label: "analyzing", color: "#58A6FF", icon: "\u25C8" },
  { label: "researching", color: "#22D3EE", icon: "\u26A1" },
  { label: "composing", color: "#A78BFA", icon: "\u2B21" },
];

export const ThinkingIndicator = memo(function ThinkingIndicator({ agents, personalities }: ThinkingIndicatorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const elapsedRef = useRef<HTMLSpanElement>(null);
  const phaseIconRef = useRef<HTMLSpanElement>(null);
  const phaseLabelRef = useRef<HTMLSpanElement>(null);
  const startRef = useRef(Date.now());
  const phaseIdxRef = useRef(0);

  // Reset start time when agents change
  const agentsKey = agents.length > 0 ? agents[0] + agents.length : "";
  useEffect(() => {
    startRef.current = Date.now();
    phaseIdxRef.current = 0;
  }, [agentsKey]);

  // Ref-based elapsed timer -- updates DOM directly, no re-renders
  useEffect(() => {
    const timer = setInterval(() => {
      const el = elapsedRef.current;
      if (!el) return;
      const secs = Math.floor((Date.now() - startRef.current) / 1000);
      el.textContent = secs > 0 ? `${secs}s` : "";
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Ref-based phase rotation -- updates DOM directly, no re-renders
  useEffect(() => {
    const phaseTimer = setInterval(() => {
      phaseIdxRef.current = (phaseIdxRef.current + 1) % THINKING_PHASES.length;
      const phase = THINKING_PHASES[phaseIdxRef.current];
      const iconEl = phaseIconRef.current;
      const labelEl = phaseLabelRef.current;
      const container = containerRef.current;
      if (iconEl) {
        iconEl.textContent = phase.icon;
        iconEl.style.color = phase.color;
      }
      if (labelEl) {
        labelEl.textContent = `${phase.label}...`;
        labelEl.style.color = phase.color;
      }
      if (container) {
        container.style.background = `${phase.color}06`;
        container.style.borderColor = `${phase.color}15`;
      }
    }, 3000);
    return () => clearInterval(phaseTimer);
  }, []);

  const getAgent = useCallback((name: string) =>
    personalities[name] || {
      display_name: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      avatar: "\u{1F916}",
    }, [personalities]);

  if (agents.length === 0) return null;

  const phase = THINKING_PHASES[0]; // initial phase for SSR

  const agentNames =
    agents.length === 1
      ? getAgent(agents[0]).display_name
      : agents.length === 2
        ? `${getAgent(agents[0]).display_name} & ${getAgent(agents[1]).display_name}`
        : `${agents.length} agents`;

  return (
    <div
      ref={containerRef}
      className="flex items-center gap-3 px-4 py-2.5 rounded-xl border transition-all duration-500"
      style={{
        background: `${phase.color}06`,
        borderColor: `${phase.color}15`,
      }}
    >
      {/* Stacked avatars with glow */}
      <div className="flex -space-x-1.5">
        {agents.slice(0, 4).map((name, i) => (
          <span
            key={name}
            className="inline-flex items-center justify-center h-6 w-6 rounded-full text-[11px] transition-all bg-muted border-2 border-card"
            style={{
              animation: `gentleBounce 1.5s ease-in-out ${i * 200}ms infinite`,
            }}
            title={getAgent(name).display_name}
          >
            {getAgent(name).avatar}
          </span>
        ))}
        {agents.length > 4 && (
          <span className="inline-flex items-center justify-center h-6 w-6 rounded-full text-[8px] font-bold data-mono bg-muted border-2 border-card text-muted-foreground">
            +{agents.length - 4}
          </span>
        )}
      </div>

      {/* Label with phase */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span
            ref={phaseIconRef}
            className="text-[10px] transition-colors duration-500"
            style={{ color: phase.color }}
          >
            {phase.icon}
          </span>
          <span className="text-[11px] font-medium truncate text-muted-foreground">
            {agentNames}
          </span>
          <span
            ref={phaseLabelRef}
            className="text-[10px] transition-colors duration-500"
            style={{ color: phase.color }}
          >
            {phase.label}...
          </span>
        </div>
      </div>

      {/* Elapsed time -- updated via ref, not state */}
      <span
        ref={elapsedRef}
        className="text-[9px] data-mono shrink-0 text-muted-foreground"
      />

      {/* Animated wave dots */}
      <div className="flex items-center gap-[3px] shrink-0">
        {[0, 120, 240].map((delay) => (
          <span
            key={delay}
            className="block h-[5px] w-[5px] rounded-full transition-colors duration-500 opacity-70"
            style={{
              background: phase.color,
              animation: `pulse-ring 1.2s ease-in-out ${delay}ms infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
});
