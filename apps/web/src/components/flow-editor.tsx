"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useFlowConfig } from "@/lib/use-flow-config";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  highlightActiveLineGutter,
  drawSelection,
  dropCursor,
  rectangularSelection,
  crosshairCursor,
} from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { yaml } from "@codemirror/lang-yaml";
import { oneDark } from "@codemirror/theme-one-dark";
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
} from "@codemirror/commands";
import {
  bracketMatching,
  indentOnInput,
  foldGutter,
  foldKeymap,
} from "@codemirror/language";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import {
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  completionKeymap,
} from "@codemirror/autocomplete";

/* ===================================================
   Types
   =================================================== */

interface ParsedAgent {
  name: string;
  display_name: string;
  model: string;
  temperature: number;
  max_tokens: number;
  min_tool_calls: number;
  tools: string[];
  requires_approval: boolean;
  is_specialist: boolean;
  prompt_preview: string;
}

interface ParsedRouting {
  examples: { input: string; route: string }[];
  fallbacks: { condition: string; route: string[] }[];
}

type Tab = "editor" | "graph" | "agents";

/* ===================================================
   Robust line-by-line YAML parser
   =================================================== */

function parseAgentsFromYaml(text: string): ParsedAgent[] {
  const lines = text.split("\n");
  const agents: ParsedAgent[] = [];

  // Find the `agents:` top-level key
  let i = 0;
  while (i < lines.length && !/^agents:\s*$/.test(lines[i])) i++;
  if (i >= lines.length) return agents;
  i++; // skip past `agents:`

  // Collect each agent block (starts with exactly 2-space indent + word + colon)
  while (i < lines.length) {
    const line = lines[i];
    // Stop if we hit another top-level key (no leading space)
    if (/^\S/.test(line) && line.trim() !== "") break;

    const agentNameMatch = line.match(/^  (\w+):\s*$/);
    if (!agentNameMatch) {
      i++;
      continue;
    }

    const name = agentNameMatch[1];
    i++;

    // Collect all lines belonging to this agent (indented >=4 spaces)
    const blockLines: string[] = [];
    while (i < lines.length) {
      const l = lines[i];
      // Another agent at same level or top-level key -> stop
      if (/^  \w+:\s*$/.test(l) || (/^\S/.test(l) && l.trim() !== "")) break;
      blockLines.push(l);
      i++;
    }

    const block = blockLines.join("\n");

    const get = (key: string, fallback: string = ""): string => {
      const m = block.match(new RegExp(`^\\s{4}${key}:\\s*(.+)`, "m"));
      return m ? m[1].trim() : fallback;
    };

    const getTools = (): string[] => {
      const m = block.match(/^\s{4}tools:\s*\[([^\]]*)\]/m);
      if (m) {
        return m[1]
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
      }
      return [];
    };

    // Grab first 2 non-empty lines of prompt
    const promptIdx = blockLines.findIndex((l) => /^\s{4}prompt:\s*\|/.test(l));
    let promptPreview = "";
    if (promptIdx >= 0) {
      const promptLines: string[] = [];
      for (let p = promptIdx + 1; p < blockLines.length && promptLines.length < 3; p++) {
        const pl = blockLines[p];
        if (/^\s{4}\w+:/.test(pl)) break; // next property
        const trimmed = pl.replace(/^\s{6}/, "").trim();
        if (trimmed) promptLines.push(trimmed);
      }
      promptPreview = promptLines.join(" ").substring(0, 140);
    }

    agents.push({
      name,
      display_name: get("display_name", name),
      model: get("model", "default"),
      temperature: parseFloat(get("temperature", "0.5")),
      max_tokens: parseInt(get("max_tokens", "2048"), 10),
      min_tool_calls: parseInt(get("min_tool_calls", "0"), 10),
      tools: getTools(),
      requires_approval: get("requires_approval") === "true",
      is_specialist: get("is_specialist") !== "false",
      prompt_preview: promptPreview,
    });
  }

  return agents;
}

function parseRoutingFromYaml(text: string): ParsedRouting {
  const examples: { input: string; route: string }[] = [];
  const fallbacks: { condition: string; route: string[] }[] = [];

  const inputMatches = [...text.matchAll(/input:\s*"([^"]+)"/g)];
  const routeStrMatches = [...text.matchAll(/route:\s*"([^"]+)"/g)];
  for (let i = 0; i < inputMatches.length; i++) {
    examples.push({
      input: inputMatches[i][1],
      route: routeStrMatches[i]?.[1] || "",
    });
  }

  const condMatches = [...text.matchAll(/condition:\s*"([^"]+)"/g)];
  const routeListMatches = [...text.matchAll(/route:\s*\[([^\]]+)\]/g)];
  for (let i = 0; i < condMatches.length; i++) {
    fallbacks.push({
      condition: condMatches[i][1],
      route: routeListMatches[i]?.[1].split(",").map((s) => s.trim()) || [],
    });
  }

  return { examples, fallbacks };
}

/* ===================================================
   Colors
   =================================================== */

const AGENT_COLORS: Record<string, string> = {
  job_intake: "#60A5FA",
  resume_tailor: "#C084FC",
  recruiter_chat: "#F472B6",
  interview_prep: "#34D399",
  leetcode_coach: "#FB923C",
  respond: "#94A3B8",
};

function agentColor(name: string): string {
  return AGENT_COLORS[name] || "#58A6FF";
}

/* ===================================================
   Main Component
   =================================================== */

interface FlowEditorProps {
  onClose: () => void;
}

export default function FlowEditor({ onClose }: FlowEditorProps) {
  const { yaml: yamlText, setYaml, save, reset, isSaving, isLoading, error, isDirty } =
    useFlowConfig();

  const [activeTab, setActiveTab] = useState<Tab>("graph");
  const [saveResult, setSaveResult] = useState<{
    ok: boolean;
    agents?: string[];
    error?: string;
  } | null>(null);
  const [yamlError, setYamlError] = useState<string | null>(null);

  const agents = useMemo(() => parseAgentsFromYaml(yamlText), [yamlText]);
  const routing = useMemo(() => parseRoutingFromYaml(yamlText), [yamlText]);

  const validateYaml = useCallback((text: string) => {
    if (!text.trim()) return setYamlError("YAML is empty");
    if (!text.includes("agents:")) return setYamlError("Missing 'agents:' key");
    setYamlError(null);
  }, []);

  async function handleSave() {
    setSaveResult(null);
    const result = await save();
    setSaveResult(result);
    if (result.ok) setTimeout(() => setSaveResult(null), 3000);
  }

  async function handleReset() {
    setSaveResult(null);
    setYamlError(null);
    await reset();
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (isDirty && !isSaving) handleSave();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, isSaving, yamlText]);

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "graph", label: "Graph" },
    { id: "agents", label: "Agents", count: agents.length },
    { id: "editor", label: "YAML" },
  ];

  return (
    <div className="flex h-full flex-col bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted">
        <div className="flex items-center gap-3">
          <svg className="h-4 w-4 text-primary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span className="text-sm font-semibold text-foreground">Flow Config</span>
          {isDirty ? (
            <Badge variant="warning" className="text-[10px]">Unsaved</Badge>
          ) : (
            <Badge variant="success" className="text-[10px]">Active</Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="ghost" size="sm" onClick={handleReset} disabled={isLoading || isSaving} className="text-[11px]">Reset</Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving || isLoading || !isDirty}
            className={cn("text-[11px] font-semibold", !isDirty && "bg-primary/15 text-primary")}
          >
            {isSaving ? "Saving..." : "Save"}
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose} className="ml-1 h-7 w-7 text-muted-foreground" title="Close">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </Button>
        </div>
      </div>

      {/* Toast */}
      {(error || yamlError || saveResult) && (
        <div className="px-4 py-1.5 border-b">
          {error && <div className="rounded-md px-3 py-1.5 text-[11px] bg-destructive/10 text-destructive">{error}</div>}
          {yamlError && !error && <div className="rounded-md px-3 py-1.5 text-[11px] bg-warning/10 text-warning">{yamlError}</div>}
          {saveResult?.ok && <div className="rounded-md px-3 py-1.5 text-[11px] bg-success/10 text-success">Config saved. Agents: {saveResult.agents?.join(", ")}</div>}
          {saveResult && !saveResult.ok && <div className="rounded-md px-3 py-1.5 text-[11px] bg-destructive/10 text-destructive">{saveResult.error}</div>}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-0 px-4 border-b bg-muted">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "relative flex items-center gap-1.5 px-3.5 py-2.5 text-[11px] font-semibold tracking-wide transition-colors",
              activeTab === tab.id ? "text-foreground" : "text-muted-foreground"
            )}
          >
            {tab.label}
            {tab.count != null && (
              <span className={cn(
                "rounded-full px-1.5 text-[9px]",
                activeTab === tab.id ? "bg-primary text-primary-foreground" : "bg-muted-foreground/10 text-muted-foreground"
              )}>{tab.count}</span>
            )}
            {activeTab === tab.id && <div className="absolute bottom-0 left-2 right-2 h-[2px] rounded-full bg-primary" />}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <svg className="h-5 w-5 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : activeTab === "editor" ? (
          <YamlEditorTab yamlText={yamlText} setYaml={setYaml} validateYaml={validateYaml} />
        ) : activeTab === "graph" ? (
          <GraphTab agents={agents} routing={routing} />
        ) : (
          <AgentsTab agents={agents} />
        )}
      </div>
    </div>
  );
}

/* ===================================================
   YAML Editor Tab (CodeMirror kept as-is)
   =================================================== */

function YamlEditorTab({ yamlText, setYaml, validateYaml }: { yamlText: string; setYaml: (v: string) => void; validateYaml: (v: string) => void }) {
  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);

  useEffect(() => {
    if (!editorRef.current || viewRef.current) return;
    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const text = update.state.doc.toString();
        setYaml(text);
        validateYaml(text);
      }
    });

    const state = EditorState.create({
      doc: yamlText,
      extensions: [
        lineNumbers(), highlightActiveLine(), highlightActiveLineGutter(), foldGutter(),
        drawSelection(), dropCursor(), rectangularSelection(), crosshairCursor(),
        indentOnInput(), bracketMatching(), closeBrackets(), autocompletion(),
        highlightSelectionMatches(), history(),
        keymap.of([...defaultKeymap, ...historyKeymap, ...foldKeymap, ...searchKeymap, ...closeBracketsKeymap, ...completionKeymap, indentWithTab]),
        yaml(), oneDark, updateListener, EditorView.lineWrapping,
        EditorView.theme({
          "&": { height: "100%", fontSize: "12.5px" },
          "&.cm-focused": { outline: "none" },
          ".cm-scroller": { overflow: "auto", fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace", lineHeight: "1.65" },
          ".cm-content": { padding: "16px 0", caretColor: "#58A6FF" },
          ".cm-cursor, .cm-dropCursor": { borderLeftColor: "#58A6FF", borderLeftWidth: "2px" },
          ".cm-gutters": { background: "#0E0E14", borderRight: "1px solid rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.2)", minWidth: "48px" },
          ".cm-activeLineGutter": { background: "rgba(88,166,255,0.08)", color: "rgba(255,255,255,0.5)" },
          ".cm-activeLine": { background: "rgba(88,166,255,0.05)" },
          ".cm-selectionBackground": { background: "rgba(88,166,255,0.18) !important" },
          ".cm-foldGutter .cm-gutterElement": { padding: "0 4px", cursor: "pointer" },
          ".cm-foldPlaceholder": { background: "rgba(88,166,255,0.12)", border: "1px solid rgba(88,166,255,0.25)", color: "#58A6FF", borderRadius: "3px", padding: "0 6px", margin: "0 4px" },
          ".cm-tooltip": { background: "#141419", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" },
          ".cm-searchMatch": { background: "rgba(88,166,255,0.2)", borderRadius: "2px" },
        }),
      ],
    });

    viewRef.current = new EditorView({ state, parent: editorRef.current });
    return () => { viewRef.current?.destroy(); viewRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const cur = view.state.doc.toString();
    if (cur !== yamlText) view.dispatch({ changes: { from: 0, to: cur.length, insert: yamlText } });
  }, [yamlText]);

  return <div ref={editorRef} className="h-full w-full overflow-hidden" />;
}

/* ===================================================
   Graph Tab -- SVG DAG with HTML overlays
   =================================================== */

function GraphTab({ agents, routing }: { agents: ParsedAgent[]; routing: ParsedRouting }) {
  const specialists = agents.filter((a) => a.is_specialist);
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null);

  // Layout
  const nodeW = 130;
  const nodeH = 56;
  const specGap = 16;
  const specCount = Math.max(specialists.length, 1);
  const totalSpecW = specCount * nodeW + (specCount - 1) * specGap;
  const canvasW = Math.max(totalSpecW + 80, 500);
  const midX = canvasW / 2;

  // Y layers
  const Y = { start: 30, coach: 100, spec: 200, merge: 310, approve: 390, respond: 470, end: 545 };
  const canvasH = Y.end + 40;

  // Specialist positions
  const specStartX = midX - totalSpecW / 2;
  const specPos = specialists.map((_, i) => ({
    x: specStartX + i * (nodeW + specGap),
    y: Y.spec,
  }));

  // Arrow marker id
  const markerId = "arrow-head";

  return (
    <div className="h-full overflow-auto bg-card">
      {/* Info bar */}
      <div className="px-4 pt-3 pb-1 flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground">
          {specialists.length} specialist{specialists.length !== 1 ? "s" : ""} running in parallel via Send()
        </p>
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground/70">
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0 border-t border-border" /> primary</span>
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0 border-t border-dashed border-border" /> conditional</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-warning" /> approval</span>
        </div>
      </div>

      <div className="flex justify-center px-4 pb-4">
        <svg width={canvasW} height={canvasH} viewBox={`0 0 ${canvasW} ${canvasH}`} className="block">
          <defs>
            <marker id={markerId} markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L8,3 L0,6" fill="rgba(255,255,255,0.25)" />
            </marker>
            <marker id="arrow-color" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L8,3 L0,6" fill="rgba(88,166,255,0.5)" />
            </marker>
            {/* Subtle grid dots */}
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="0.5" fill="rgba(255,255,255,0.03)" />
            </pattern>
          </defs>

          {/* Background grid */}
          <rect width={canvasW} height={canvasH} fill="url(#grid)" />

          {/* -- EDGES -- */}

          {/* START -> Coach */}
          <Edge x1={midX} y1={Y.start + 28} x2={midX} y2={Y.coach} />

          {/* Coach -> each specialist (fan-out) */}
          {specPos.map((pos, i) => (
            <Edge key={`c-s-${i}`} x1={midX} y1={Y.coach + nodeH} x2={pos.x + nodeW / 2} y2={pos.y} color={agentColor(specialists[i].name)} highlight={hoveredAgent === specialists[i].name} />
          ))}

          {/* Each specialist -> merge */}
          {specPos.map((pos, i) => (
            <Edge key={`s-m-${i}`} x1={pos.x + nodeW / 2} y1={pos.y + nodeH} x2={midX} y2={Y.merge} color={agentColor(specialists[i].name)} highlight={hoveredAgent === specialists[i].name} />
          ))}

          {/* Merge -> Approval Gate */}
          <Edge x1={midX} y1={Y.merge + 36} x2={midX} y2={Y.approve} label="has approvals" />

          {/* Merge -> Respond (skip approval, dashed) */}
          <Edge x1={midX + 60} y1={Y.merge + 18} x2={midX + nodeW / 2 + 10} y2={Y.respond + 10} dashed label="no approvals" />

          {/* Coach -> Respond (respond-only, dashed) */}
          <Edge x1={midX - nodeW / 2 - 10} y1={Y.coach + nodeH / 2} x2={midX - nodeW / 2 - 10} y2={Y.respond + nodeH / 2} dashed label="respond only" />

          {/* Approval -> Respond */}
          <Edge x1={midX} y1={Y.approve + 40} x2={midX} y2={Y.respond} />

          {/* Respond -> END */}
          <Edge x1={midX} y1={Y.respond + nodeH} x2={midX} y2={Y.end} />

          {/* -- NODES -- */}

          {/* START pill */}
          <g>
            <rect x={midX - 36} y={Y.start} width={72} height={28} rx={14} fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.12)" strokeWidth={1} />
            <text x={midX} y={Y.start + 15} textAnchor="middle" dominantBaseline="central" fill="rgba(255,255,255,0.5)" fontSize={10} fontWeight={600} fontFamily="system-ui">START</text>
          </g>

          {/* Coach */}
          <DagNode x={midX - nodeW / 2} y={Y.coach} w={nodeW} h={nodeH} label="Coach" sublabel="Router" color="#58A6FF" icon="router" />

          {/* Specialist nodes */}
          {specialists.map((agent, i) => {
            const pos = specPos[i];
            const c = agentColor(agent.name);
            const hovered = hoveredAgent === agent.name;
            return (
              <g key={agent.name} onMouseEnter={() => setHoveredAgent(agent.name)} onMouseLeave={() => setHoveredAgent(null)} style={{ cursor: "default" }}>
                {/* Glow on hover */}
                {hovered && <rect x={pos.x - 3} y={pos.y - 3} width={nodeW + 6} height={nodeH + 6} rx={12} fill="none" stroke={c} strokeWidth={1} strokeOpacity={0.3} />}
                <rect x={pos.x} y={pos.y} width={nodeW} height={nodeH} rx={10} fill={`${c}12`} stroke={`${c}${hovered ? "60" : "30"}`} strokeWidth={1} />
                {/* Top accent bar */}
                <rect x={pos.x + 8} y={pos.y} width={nodeW - 16} height={2.5} rx={1.25} fill={`${c}${hovered ? "90" : "50"}`} />
                {/* Name */}
                <text x={pos.x + nodeW / 2} y={pos.y + 20} textAnchor="middle" fill={c} fontSize={11} fontWeight={600} fontFamily="system-ui">{agent.display_name}</text>
                {/* Meta */}
                <text x={pos.x + nodeW / 2} y={pos.y + 35} textAnchor="middle" fill="rgba(255,255,255,0.35)" fontSize={9} fontFamily="system-ui">{agent.model} · {agent.tools.length} tools</text>
                {/* Tool calls badge */}
                {agent.min_tool_calls > 0 && (
                  <g>
                    <rect x={pos.x + nodeW / 2 - 20} y={pos.y + 42} width={40} height={14} rx={7} fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.08)" strokeWidth={0.5} />
                    <text x={pos.x + nodeW / 2} y={pos.y + 50} textAnchor="middle" dominantBaseline="central" fill="rgba(255,255,255,0.4)" fontSize={8} fontFamily="system-ui">min {agent.min_tool_calls} calls</text>
                  </g>
                )}
                {/* Approval indicator */}
                {agent.requires_approval && (
                  <g>
                    <circle cx={pos.x + nodeW - 6} cy={pos.y + 6} r={6} fill="#E3B341" fillOpacity={0.15} stroke="#E3B341" strokeWidth={0.8} strokeOpacity={0.4} />
                    <text x={pos.x + nodeW - 6} y={pos.y + 7} textAnchor="middle" dominantBaseline="central" fill="#E3B341" fontSize={8} fontWeight={700}>!</text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Merge */}
          <g>
            <rect x={midX - 50} y={Y.merge} width={100} height={36} rx={18} fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.1)" strokeWidth={1} />
            <text x={midX} y={Y.merge + 19} textAnchor="middle" dominantBaseline="central" fill="rgba(255,255,255,0.45)" fontSize={10} fontWeight={500} fontFamily="system-ui">merge</text>
          </g>

          {/* Approval Gate */}
          <g>
            <rect x={midX - 62} y={Y.approve} width={124} height={40} rx={10} fill="rgba(251,191,36,0.06)" stroke="rgba(251,191,36,0.2)" strokeWidth={1} />
            <text x={midX} y={Y.approve + 14} textAnchor="middle" fill="#E3B341" fontSize={10} fontWeight={600} fontFamily="system-ui">Approval Gate</text>
            <text x={midX} y={Y.approve + 28} textAnchor="middle" fill="rgba(251,191,36,0.5)" fontSize={8} fontFamily="system-ui">interrupt()</text>
          </g>

          {/* Respond */}
          <DagNode x={midX - nodeW / 2} y={Y.respond} w={nodeW} h={nodeH} label="Respond" sublabel="Compose output" color="#94A3B8" />

          {/* END pill */}
          <g>
            <rect x={midX - 30} y={Y.end} width={60} height={28} rx={14} fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.12)" strokeWidth={1} />
            <text x={midX} y={Y.end + 15} textAnchor="middle" dominantBaseline="central" fill="rgba(255,255,255,0.5)" fontSize={10} fontWeight={600} fontFamily="system-ui">END</text>
          </g>

          {/* Parallel bracket annotation */}
          {specCount > 1 && (
            <g>
              <line x1={specStartX - 12} y1={Y.spec + 4} x2={specStartX - 12} y2={Y.spec + nodeH - 4} stroke="rgba(255,255,255,0.1)" strokeWidth={1.5} strokeLinecap="round" />
              <line x1={specStartX - 12} y1={Y.spec + 4} x2={specStartX - 6} y2={Y.spec + 4} stroke="rgba(255,255,255,0.1)" strokeWidth={1.5} strokeLinecap="round" />
              <line x1={specStartX - 12} y1={Y.spec + nodeH - 4} x2={specStartX - 6} y2={Y.spec + nodeH - 4} stroke="rgba(255,255,255,0.1)" strokeWidth={1.5} strokeLinecap="round" />
              <text x={specStartX - 16} y={Y.spec + nodeH / 2} textAnchor="end" dominantBaseline="central" fill="rgba(255,255,255,0.15)" fontSize={9} fontFamily="system-ui" transform={`rotate(-90 ${specStartX - 16} ${Y.spec + nodeH / 2})`}>parallel</text>
            </g>
          )}
        </svg>
      </div>

      {/* Routing examples */}
      {routing.examples.length > 0 && (
        <div className="px-4 pb-6">
          <h3 className="text-[10px] font-semibold tracking-wider mb-2.5 text-muted-foreground/70">ROUTING EXAMPLES</h3>
          <div className="space-y-1">
            {routing.examples.map((ex, i) => (
              <div key={i} className="flex items-center gap-2.5 rounded-lg px-3 py-2 bg-muted border">
                <span className="text-[11px] shrink-0 text-muted-foreground">&ldquo;{ex.input}&rdquo;</span>
                <svg className="h-3 w-3 shrink-0 text-muted-foreground/70" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                <div className="flex flex-wrap gap-1">
                  {ex.route.split(",").map((r) => {
                    const name = r.trim();
                    const c = agentColor(name);
                    return <span key={name} className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: `${c}15`, color: c, border: `1px solid ${c}25` }}>{name}</span>;
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* SVG helper components */

function Edge({ x1, y1, x2, y2, color, dashed, highlight, label }: { x1: number; y1: number; x2: number; y2: number; color?: string; dashed?: boolean; highlight?: boolean; label?: string }) {
  const stroke = color ? (highlight ? color : `${color}40`) : `rgba(255,255,255,${dashed ? "0.08" : "0.15"})`;
  const sw = highlight ? 2 : 1.5;

  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;

  if (Math.abs(x1 - x2) < 2) {
    return (
      <g>
        <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={stroke} strokeWidth={sw} strokeDasharray={dashed ? "5,4" : undefined} markerEnd={dashed ? undefined : "url(#arrow-head)"} />
        {label && <text x={x1 + 8} y={my} fill="rgba(255,255,255,0.2)" fontSize={8} fontFamily="system-ui">{label}</text>}
      </g>
    );
  }

  const cy1 = y1 + (y2 - y1) * 0.4;
  const cy2 = y1 + (y2 - y1) * 0.6;
  const d = `M${x1},${y1} C${x1},${cy1} ${x2},${cy2} ${x2},${y2}`;
  return (
    <g>
      <path d={d} fill="none" stroke={stroke} strokeWidth={sw} strokeDasharray={dashed ? "5,4" : undefined} />
      {label && <text x={mx + 6} y={my} fill="rgba(255,255,255,0.2)" fontSize={8} fontFamily="system-ui">{label}</text>}
    </g>
  );
}

function DagNode({ x, y, w, h, label, sublabel, color, icon }: { x: number; y: number; w: number; h: number; label: string; sublabel: string; color: string; icon?: string }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} fill={`${color}10`} stroke={`${color}30`} strokeWidth={1} />
      {icon === "router" && (
        <g transform={`translate(${x + 12},${y + h / 2 - 6})`}>
          <circle cx="6" cy="6" r="5" fill="none" stroke={`${color}50`} strokeWidth={1} />
          <circle cx="6" cy="6" r="2" fill={`${color}60`} />
        </g>
      )}
      <text x={x + w / 2} y={y + 22} textAnchor="middle" fill={color} fontSize={11} fontWeight={600} fontFamily="system-ui">{label}</text>
      <text x={x + w / 2} y={y + 38} textAnchor="middle" fill={`${color}60`} fontSize={9} fontFamily="system-ui">{sublabel}</text>
    </g>
  );
}

/* ===================================================
   Agents Tab -- Cards
   =================================================== */

function AgentsTab({ agents }: { agents: ParsedAgent[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="h-full overflow-auto px-4 py-4 space-y-2 bg-card">
      {agents.map((agent) => {
        const color = agentColor(agent.name);
        const isOpen = expanded === agent.name;

        return (
          <div key={agent.name} className={cn("rounded-xl overflow-hidden transition-all duration-200 bg-muted border", isOpen && `border-[${color}30]`)}>
            <button
              onClick={() => setExpanded(isOpen ? null : agent.name)}
              className="w-full flex items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex items-center gap-3">
                <div className="h-2.5 w-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}40` }} />
                <div>
                  <span className="text-xs font-semibold text-foreground">{agent.display_name}</span>
                  <span className="ml-2 text-[10px] font-mono text-muted-foreground/70">{agent.name}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-muted-foreground/70">{agent.tools.length} tools</span>
                {agent.requires_approval && <Badge variant="warning" className="text-[9px]">APPROVAL</Badge>}
                {!agent.is_specialist && <Badge variant="secondary" className="text-[9px]">FALLBACK</Badge>}
                <svg className={cn("h-3.5 w-3.5 transition-transform duration-200 text-muted-foreground", isOpen && "rotate-180")} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </button>

            {isOpen && (
              <div className="px-4 pb-4 pt-1 space-y-3 border-t" style={{ borderColor: `${color}10` }}>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { label: "Model", value: agent.model },
                    { label: "Temp", value: agent.temperature.toFixed(1) },
                    { label: "Max Tokens", value: agent.max_tokens.toLocaleString() },
                    { label: "Min Calls", value: String(agent.min_tool_calls) },
                  ].map((item) => (
                    <div key={item.label} className="rounded-lg px-2.5 py-1.5 text-center bg-background/50 border">
                      <div className="text-[9px] font-medium text-muted-foreground/70">{item.label}</div>
                      <div className="text-[11px] font-mono font-semibold mt-0.5 text-foreground">{item.value}</div>
                    </div>
                  ))}
                </div>

                {agent.tools.length > 0 && (
                  <div>
                    <span className="text-[10px] font-semibold block mb-1.5 text-muted-foreground/70">TOOLS</span>
                    <div className="flex flex-wrap gap-1">
                      {agent.tools.map((tool) => (
                        <Badge key={tool} variant="secondary" className="text-[10px] font-mono">{tool}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {agent.prompt_preview && (
                  <div>
                    <span className="text-[10px] font-semibold block mb-1.5 text-muted-foreground/70">SYSTEM PROMPT</span>
                    <div className="rounded-lg px-3 py-2 text-[11px] leading-relaxed bg-background/50 text-muted-foreground border">
                      {agent.prompt_preview}{agent.prompt_preview.length >= 140 ? "..." : ""}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
