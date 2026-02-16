"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { AgentAvatar, getAgentConfig } from "./agent-avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const AVAILABLE_AGENTS = [
  "oracle",
  "architect",
  "pathfinder",
  "strategist",
  "cipher",
  "forge",
  "catalyst",
  "sentinel",
  "compass",
  "nexus",
];

interface AgentSuggestion {
  agent: string;
  relevance_score: number;
  reason: string;
  expertise_match: string[];
}

const AVAILABLE_TOOLS = [
  { id: "web_search", name: "Web Search", description: "Search the web for real-time information", icon: "\uD83D\uDD0D" },
  { id: "tag_agent_in_chat", name: "Tag Agent", description: "Mention other agents in discussion", icon: "\uD83D\uDCAC" },
  { id: "propose_prompt_change", name: "Self-Modify", description: "Propose changes to own system prompt", icon: "\uD83E\uDDEC" },
  { id: "review_resume", name: "Review Resume", description: "Access user's resume data", icon: "\uD83D\uDCC4" },
  { id: "get_saved_jobs", name: "Saved Jobs", description: "Access user's saved job listings", icon: "\uD83D\uDCBC" },
  { id: "get_job_pipeline", name: "Job Pipeline", description: "View job application pipeline", icon: "\uD83D\uDCCA" },
];

export interface GroupChatConfig {
  maxTurns: number;
  allowedTools: string[];
}

interface StartChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStart: (topic: string, participants: string[], config: GroupChatConfig) => Promise<void>;
}

export function StartChatModal({ isOpen, onClose, onStart }: StartChatModalProps) {
  const [topic, setTopic] = useState("");
  const [selectedAgents, setSelectedAgents] = useState<string[]>(["oracle", "architect"]);
  const [isLoading, setIsLoading] = useState(false);
  const [maxTurns, setMaxTurns] = useState(10);
  const [selectedTools, setSelectedTools] = useState<string[]>(["web_search", "tag_agent_in_chat", "propose_prompt_change"]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [suggestions, setSuggestions] = useState<AgentSuggestion[]>([]);
  const [isSuggestingAgents, setIsSuggestingAgents] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch agent suggestions when topic changes
  const fetchSuggestions = useCallback(async (topicText: string) => {
    if (topicText.length < 5) {
      setSuggestions([]);
      return;
    }

    setIsSuggestingAgents(true);
    try {
      const res = await fetch("/api/ai/group-chats/suggest-agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topicText, exclude: [], max: 4 }),
      });

      if (res.ok) {
        const data = await res.json();
        setSuggestions(data.suggestions || []);

        // Auto-select suggested agents if user hasn't manually selected
        if (data.default_participants?.length >= 2) {
          setSelectedAgents(data.default_participants);
        }
      }
    } catch (err) {
      console.error("Failed to fetch suggestions:", err);
    } finally {
      setIsSuggestingAgents(false);
    }
  }, []);

  // Debounced topic change handler
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      if (topic) {
        fetchSuggestions(topic);
      }
    }, 500);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [topic, fetchSuggestions]);

  const toggleAgent = (agent: string) => {
    setSelectedAgents((prev) =>
      prev.includes(agent)
        ? prev.filter((a) => a !== agent)
        : prev.length < 6
        ? [...prev, agent]
        : prev
    );
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId)
        ? prev.filter((t) => t !== toolId)
        : [...prev, toolId]
    );
  };

  const handleStart = async () => {
    if (!topic.trim() || selectedAgents.length < 2) return;
    setIsLoading(true);
    try {
      await onStart(topic.trim(), selectedAgents, {
        maxTurns,
        allowedTools: selectedTools,
      });
      setTopic("");
      setShowAdvanced(false);
      onClose();
    } catch (e) {
      console.error("Failed to start chat:", e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Start Group Discussion</DialogTitle>
          <DialogDescription>
            Agents will discuss and debate the topic autonomously
          </DialogDescription>
        </DialogHeader>

        {/* Content */}
        <div className="space-y-5">
          {/* Topic */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider mb-2 text-muted-foreground">
              Topic
            </label>
            <Textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="What should the agents discuss? Be specific for better results..."
              className="resize-none text-[14px]"
              rows={3}
            />
          </div>

          {/* Agent Suggestions (shown when typing topic) */}
          {suggestions.length > 0 && (
            <div className="p-3 rounded-xl bg-primary/5 border border-primary/20">
              <div className="flex items-center gap-2 mb-2">
                {isSuggestingAgents ? (
                  <div className="h-3 w-3 rounded-full border border-t-transparent border-primary animate-spin" />
                ) : (
                  <svg className="h-3.5 w-3.5 text-primary" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                  </svg>
                )}
                <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                  Suggested Experts
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => {
                  const config = getAgentConfig(s.agent);
                  const isSelected = selectedAgents.includes(s.agent);
                  return (
                    <button
                      key={s.agent}
                      onClick={() => toggleAgent(s.agent)}
                      className={cn(
                        "flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] transition-all",
                        !isSelected && "bg-card text-muted-foreground"
                      )}
                      style={isSelected ? { background: config.color, color: "white" } : undefined}
                      title={s.reason}
                    >
                      <span>{config.name}</span>
                      {s.expertise_match.length > 0 && (
                        <span className="opacity-60">({s.expertise_match[0]})</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Participants */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider mb-2 text-muted-foreground">
              Participants ({selectedAgents.length}/6)
            </label>
            <div className="grid grid-cols-2 gap-2">
              {AVAILABLE_AGENTS.map((agent) => {
                const config = getAgentConfig(agent);
                const isSelected = selectedAgents.includes(agent);
                const suggestion = suggestions.find((s) => s.agent === agent);

                return (
                  <button
                    key={agent}
                    onClick={() => toggleAgent(agent)}
                    className={cn(
                      "flex items-center gap-2.5 p-2.5 rounded-xl text-left transition-all duration-200 relative border",
                      isSelected ? "border-primary/40" : suggestion ? "border-primary/20" : "border-border"
                    )}
                    style={isSelected ? { background: `${config.color}15` } : undefined}
                  >
                    {suggestion && !isSelected && (
                      <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-primary" />
                    )}
                    <AgentAvatar agent={agent} size="sm" />
                    <span
                      className={cn(
                        "text-[12px] font-medium",
                        !isSelected && "text-muted-foreground"
                      )}
                      style={isSelected ? { color: config.color } : undefined}
                    >
                      {config.name}
                    </span>
                    {isSelected && (
                      <svg
                        className="ml-auto h-4 w-4"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                        style={{ color: config.color }}
                      >
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] mt-2 text-muted-foreground">
              Select 2-6 agents to participate in the discussion
            </p>
          </div>

          {/* Advanced Settings Toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <svg
              className={cn("h-4 w-4 transition-transform", showAdvanced && "rotate-90")}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            Advanced Settings
          </button>

          {/* Advanced Settings Panel */}
          {showAdvanced && (
            <div className="space-y-5 p-4 rounded-xl border bg-card">
              {/* Max Turns */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    Max Turns
                  </label>
                  <Badge variant="info" className="text-[13px] font-semibold">
                    {maxTurns}
                  </Badge>
                </div>
                <input
                  type="range"
                  min={4}
                  max={30}
                  value={maxTurns}
                  onChange={(e) => setMaxTurns(Number(e.target.value))}
                  className="w-full accent-primary"
                />
                <div className="flex justify-between text-[10px] mt-1 text-muted-foreground">
                  <span>Quick (4)</span>
                  <span>Standard (10)</span>
                  <span>Deep (30)</span>
                </div>
              </div>

              {/* Tools */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider mb-2 text-muted-foreground">
                  Available Tools ({selectedTools.length}/{AVAILABLE_TOOLS.length})
                </label>
                <div className="space-y-2">
                  {AVAILABLE_TOOLS.map((tool) => {
                    const isSelected = selectedTools.includes(tool.id);
                    return (
                      <button
                        key={tool.id}
                        onClick={() => toggleTool(tool.id)}
                        className={cn(
                          "w-full flex items-center gap-3 p-2.5 rounded-xl text-left transition-all duration-200 border",
                          isSelected
                            ? "bg-primary/10 border-primary"
                            : "bg-muted border-transparent"
                        )}
                      >
                        <span className="text-[16px]">{tool.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className={cn(
                            "text-[12px] font-medium",
                            isSelected ? "text-primary" : "text-foreground"
                          )}>
                            {tool.name}
                          </div>
                          <div className="text-[11px] truncate text-muted-foreground">
                            {tool.description}
                          </div>
                        </div>
                        <div
                          className={cn(
                            "w-5 h-5 rounded-md flex items-center justify-center transition-colors",
                            isSelected ? "bg-primary" : "border-2 border-border"
                          )}
                        >
                          {isSelected && (
                            <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                            </svg>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleStart}
            disabled={!topic.trim() || selectedAgents.length < 2 || isLoading}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Starting...
              </span>
            ) : (
              "Start Discussion"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
