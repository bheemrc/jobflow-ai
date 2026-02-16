"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface AgentSummary {
  agent: string;
  total_genes: number;
  by_type: Record<string, number>;
}

interface Gene {
  id: number;
  agent: string;
  gene_type: string;
  name: string;
  description: string;
  confidence: number;
  decay_rate: number;
  reinforcements: number;
  source: string;
  tags: string[];
  archived: boolean;
  created_at: string;
}

const TYPE_COLORS: Record<string, string> = {
  FACT: "#58A6FF",
  BELIEF: "#A78BFA",
  SKILL: "#56D364",
  INSIGHT: "#22D3EE",
  GOAL: "#F97316",
  HUNCH: "#E3B341",
};

export default function AdminDNAPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [genes, setGenes] = useState<Gene[]>([]);
  const [loading, setLoading] = useState(true);
  const [genesLoading, setGenesLoading] = useState(false);

  // Inject gene form
  const [injectName, setInjectName] = useState("");
  const [injectType, setInjectType] = useState("FACT");
  const [injectDesc, setInjectDesc] = useState("");
  const [injectConf, setInjectConf] = useState("0.7");
  const [injecting, setInjecting] = useState(false);

  useEffect(() => {
    fetch("/api/ai/admin/dna/agents")
      .then((r) => r.json())
      .then((d) => { if (d?.agents) setAgents(d.agents); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const loadGenes = useCallback(async (agent: string) => {
    setSelectedAgent(agent);
    setGenesLoading(true);
    try {
      const r = await fetch(`/api/ai/admin/dna/agents/${agent}/genes`);
      const d = await r.json();
      if (d?.genes) setGenes(d.genes);
    } catch {
      // ignore
    } finally {
      setGenesLoading(false);
    }
  }, []);

  const handleInject = useCallback(async () => {
    if (!selectedAgent || !injectName.trim()) return;
    setInjecting(true);
    try {
      const r = await fetch(`/api/ai/admin/dna/agents/${selectedAgent}/inject-gene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: injectName.trim(),
          type: injectType,
          description: injectDesc.trim(),
          confidence: parseFloat(injectConf) || 0.7,
        }),
      });
      if (r.ok) {
        setInjectName("");
        setInjectDesc("");
        await loadGenes(selectedAgent);
      }
    } catch {
      // ignore
    } finally {
      setInjecting(false);
    }
  }, [selectedAgent, injectName, injectType, injectDesc, injectConf, loadGenes]);

  const handleKillPulse = useCallback(async (agent: string) => {
    try {
      await fetch(`/api/ai/admin/dna/agents/${agent}/kill-pulse`, { method: "POST" });
    } catch {
      // ignore
    }
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[1100px] mx-auto px-4 pt-6 pb-16">
        <h1 className="text-[22px] font-bold mb-1 text-foreground">
          DNA Control Board
        </h1>
        <p className="text-[13px] mb-6 text-muted-foreground">
          Inspect agent genomes, inject genes, manage pulse schedules.
        </p>

        <div className="grid grid-cols-[280px_1fr] gap-5">
          {/* Agent list */}
          <div>
            <h2 className="text-[12px] font-semibold uppercase tracking-wider mb-3 text-muted-foreground">
              Agents
            </h2>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="rounded-xl h-[60px] w-full" />
                ))}
              </div>
            ) : agents.length === 0 ? (
              <Card className="p-4 text-[12px] text-center text-muted-foreground">
                No agents with genes
              </Card>
            ) : (
              <div className="space-y-1.5">
                {agents.map((a) => (
                  <button
                    key={a.agent}
                    onClick={() => loadGenes(a.agent)}
                    className={cn(
                      "w-full text-left rounded-xl p-3 transition-all border",
                      selectedAgent === a.agent
                        ? "bg-primary/10 border-primary"
                        : "bg-card border-border hover:border-border"
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[13px] font-semibold text-foreground">
                        {a.agent}
                      </span>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {a.total_genes}
                      </span>
                    </div>
                    <div className="flex gap-1 flex-wrap">
                      {Object.entries(a.by_type).map(([type, count]) => (
                        <span
                          key={type}
                          className="rounded px-1.5 py-0.5 text-[9px] font-medium"
                          style={{ background: `${TYPE_COLORS[type] || "#666"}22`, color: TYPE_COLORS[type] || "#666" }}
                        >
                          {type} {count}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Gene detail panel */}
          <div>
            {!selectedAgent ? (
              <Card className="p-12 text-center text-muted-foreground">
                Select an agent to view genome
              </Card>
            ) : (
              <>
                {/* Agent header */}
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[16px] font-bold text-foreground">
                    {selectedAgent}
                  </h2>
                  <Button
                    onClick={() => handleKillPulse(selectedAgent)}
                    variant="outline"
                    size="sm"
                    className="text-[11px] text-destructive border-destructive/30 bg-destructive/10"
                  >
                    Kill Pulse
                  </Button>
                </div>

                {/* Inject gene form */}
                <Card className="p-4 mb-4">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-3 text-muted-foreground">
                    Inject Gene
                  </h3>
                  <div className="grid grid-cols-[1fr_120px_80px] gap-2 mb-2">
                    <Input
                      type="text"
                      value={injectName}
                      onChange={(e) => setInjectName(e.target.value)}
                      placeholder="Gene name (plain English)"
                      className="rounded-lg text-[12px]"
                    />
                    <select
                      value={injectType}
                      onChange={(e) => setInjectType(e.target.value)}
                      className="rounded-lg px-2 py-1.5 text-[12px] bg-background text-foreground border cursor-pointer"
                    >
                      {["FACT", "BELIEF", "SKILL", "INSIGHT", "GOAL", "HUNCH"].map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <Input
                      type="text"
                      value={injectConf}
                      onChange={(e) => setInjectConf(e.target.value)}
                      placeholder="0.7"
                      className="rounded-lg text-[12px]"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      value={injectDesc}
                      onChange={(e) => setInjectDesc(e.target.value)}
                      placeholder="Description"
                      className="flex-1 rounded-lg text-[12px]"
                    />
                    <Button
                      onClick={handleInject}
                      disabled={injecting || !injectName.trim()}
                      size="sm"
                      className="rounded-lg px-4 text-[12px]"
                    >
                      {injecting ? "..." : "Inject"}
                    </Button>
                  </div>
                </Card>

                {/* Genes table */}
                {genesLoading ? (
                  <div className="space-y-1">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Skeleton key={i} className="rounded-lg h-[44px] w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-1">
                    {genes.map((g) => (
                      <div
                        key={g.id}
                        className="rounded-lg px-3 py-2.5 flex items-center gap-3 bg-card"
                      >
                        <span
                          className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold"
                          style={{ background: `${TYPE_COLORS[g.gene_type] || "#666"}22`, color: TYPE_COLORS[g.gene_type] || "#666" }}
                        >
                          {g.gene_type}
                        </span>
                        <div className="flex-1 min-w-0">
                          <span className="text-[12px] font-medium truncate block text-foreground">
                            {g.name}
                          </span>
                          {g.description && (
                            <span className="text-[10px] truncate block text-muted-foreground">
                              {g.description}
                            </span>
                          )}
                        </div>
                        {/* Confidence bar */}
                        <div className="w-16 shrink-0">
                          <div className="h-1.5 rounded-full overflow-hidden bg-muted">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                g.confidence > 0.7 ? "bg-success" : g.confidence > 0.4 ? "bg-warning" : "bg-destructive"
                              )}
                              style={{ width: `${g.confidence * 100}%` }}
                            />
                          </div>
                          <span className="text-[9px] font-mono text-muted-foreground">
                            {(g.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        <span className="text-[9px] shrink-0 text-muted-foreground">
                          r:{g.reinforcements}
                        </span>
                        <div className="flex gap-0.5 shrink-0">
                          {g.tags.slice(0, 2).map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-[8px] px-1 py-0.5">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
