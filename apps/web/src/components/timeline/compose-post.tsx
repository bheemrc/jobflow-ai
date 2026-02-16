"use client";

import { useState, useRef, useMemo, memo } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { AgentPersonality } from "@/lib/use-timeline-events";
import { REALMS } from "@/lib/use-timeline-events";

// Intent -> agent suggestion mapping
const AGENT_INTENTS: { keywords: string[]; agents: string[]; label: string }[] = [
  { keywords: ["resume", "cv", "tailor", "format"], agents: ["forge", "resume_tailor"], label: "Resume expert" },
  { keywords: ["interview", "prep", "behavioral", "technical", "whiteboard"], agents: ["cipher", "strategist"], label: "Interview prep" },
  { keywords: ["salary", "negotiate", "offer", "compensation", "benefits"], agents: ["strategist", "advocate"], label: "Negotiation" },
  { keywords: ["company", "culture", "glassdoor", "review", "research"], agents: ["catalyst", "scout"], label: "Company intel" },
  { keywords: ["leetcode", "algorithm", "coding", "problem", "solve", "system design"], agents: ["cipher"], label: "Technical" },
  { keywords: ["apply", "application", "job", "role", "position", "search"], agents: ["pathfinder", "job_intake"], label: "Job search" },
  { keywords: ["network", "linkedin", "connect", "referral", "outreach"], agents: ["catalyst"], label: "Networking" },
  { keywords: ["anxiety", "stress", "overwhelm", "confidence", "motivat"], agents: ["mentor", "advocate"], label: "Support" },
  { keywords: ["analyze", "market", "trend", "demand", "skill"], agents: ["scout", "analyst"], label: "Market analysis" },
];

interface ComposePostProps {
  agents: Record<string, AgentPersonality>;
  onPost: (content: string) => void;
}

const FLAIRS = [
  { id: "discussion", label: "Discussion", icon: "\u{1F4AC}", color: "#60A5FA" },
  { id: "intel", label: "Intel", icon: "\u25C9", color: "#4ADE80" },
  { id: "strategy", label: "Strategy", icon: "\u265F\uFE0F", color: "#A78BFA" },
  { id: "debug", label: "Debug", icon: "\u{1F527}", color: "#F97316" },
  { id: "celebration", label: "\u{1F389}", icon: "\u{1F389}", color: "#FBBF24" },
  { id: "question", label: "Question", icon: "?", color: "#22D3EE" },
];

const QUICK_MISSIONS = [
  { icon: "\u26A1", label: "Analyze a role", template: "Analyze this role: " },
  { icon: "\u265F\uFE0F", label: "Prep for interview", template: "Help me prepare for an interview at " },
  { icon: "\u25C8", label: "Solve a problem", template: "Walk me through solving: " },
  { icon: "\u25B3", label: "Design system", template: "Design a system for: " },
  { icon: "\u25C9", label: "Market intel", template: "What's the market like for " },
  { icon: "\u{1F525}", label: "Review resume", template: "Review my resume for fit with " },
];

export const ComposePost = memo(function ComposePost({ agents, onPost }: ComposePostProps) {
  const [content, setContent] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSearch, setMentionSearch] = useState("");
  const [focused, setFocused] = useState(false);
  const [selectedRealm, setSelectedRealm] = useState<string | null>(null);
  const [selectedFlair, setSelectedFlair] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const agentNames = Object.keys(agents).filter((k) => k !== "user");

  const filteredAgents = mentionSearch
    ? agentNames.filter(
        (name) =>
          name.includes(mentionSearch.toLowerCase()) ||
          agents[name]?.display_name?.toLowerCase().includes(mentionSearch.toLowerCase())
      )
    : agentNames;

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setContent(val);
    const cursor = e.target.selectionStart;
    const textBefore = val.slice(0, cursor);
    const atMatch = textBefore.match(/@(\w*)$/);
    if (atMatch) {
      setShowMentions(true);
      setMentionSearch(atMatch[1]);
    } else {
      setShowMentions(false);
      setMentionSearch("");
    }
  };

  const insertMention = (agentName: string) => {
    if (!textareaRef.current) return;
    const cursor = textareaRef.current.selectionStart;
    const textBefore = content.slice(0, cursor);
    const textAfter = content.slice(cursor);
    const atStart = textBefore.lastIndexOf("@");
    const newText = textBefore.slice(0, atStart) + `@${agentName} ` + textAfter;
    setContent(newText);
    setShowMentions(false);
    textareaRef.current.focus();
  };

  const applyTemplate = (template: string) => {
    setContent(template);
    setFocused(true);
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const handleSubmit = () => {
    if (content.trim()) {
      onPost(content.trim());
      setContent("");
      setSelectedRealm(null);
      setSelectedFlair(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === "Escape") {
      setShowMentions(false);
    }
  };

  // Proactive agent suggestions based on content intent
  const suggestedAgents = useMemo(() => {
    if (content.length < 5) return [];
    const lower = content.toLowerCase();
    const matched = new Map<string, string>(); // agent -> label
    for (const intent of AGENT_INTENTS) {
      if (intent.keywords.some((kw) => lower.includes(kw))) {
        for (const agent of intent.agents) {
          if (!matched.has(agent) && agentNames.includes(agent) && !content.includes(`@${agent}`)) {
            matched.set(agent, intent.label);
          }
        }
      }
    }
    return [...matched.entries()].slice(0, 3).map(([name, label]) => ({ name, label }));
  }, [content, agentNames]);

  const hasContent = content.trim().length > 0;

  return (
    <Card
      className={cn(
        "rounded-2xl overflow-hidden transition-all duration-300",
        focused && "ring-2 ring-primary/20 shadow-lg"
      )}
    >
      <div className="p-4 relative">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className="flex-shrink-0 h-9 w-9 rounded-full flex items-center justify-center text-base bg-primary/10 border border-border">
            &#x1F464;
          </div>
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={content}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setTimeout(() => setFocused(false), 150)}
              placeholder="Ask anything -- agents will emerge to help..."
              rows={focused || hasContent ? 3 : 1}
              className="w-full resize-none outline-none text-[13px] leading-relaxed transition-all duration-200 bg-transparent text-foreground placeholder:text-muted-foreground"
            />

            {/* Mention autocomplete */}
            {showMentions && filteredAgents.length > 0 && (
              <Card className="absolute left-0 top-full mt-1 shadow-2xl overflow-hidden z-50 min-w-[260px] animate-fade-in-up">
                <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground border-b">
                  Summon an agent
                </div>
                {filteredAgents.slice(0, 6).map((name) => (
                  <button
                    key={name}
                    onClick={() => insertMention(name)}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors text-foreground hover:bg-accent"
                  >
                    <span className="text-base">{agents[name]?.avatar || "\u{1F916}"}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium">{agents[name]?.display_name || name}</div>
                      <div className="text-[10px] truncate text-muted-foreground">
                        @{name} -- {agents[name]?.bio?.slice(0, 50) || "AI agent"}
                      </div>
                    </div>
                  </button>
                ))}
              </Card>
            )}
          </div>
        </div>

        {/* Proactive agent suggestions -- show when typing and agents detected */}
        {hasContent && suggestedAgents.length > 0 && !showMentions && (
          <div className="mt-2.5 animate-fade-in">
            <div className="text-[9px] font-bold uppercase tracking-wider mb-1.5 text-muted-foreground">
              Suggested agents
            </div>
            <div className="flex flex-wrap gap-1.5">
              {suggestedAgents.map((s) => {
                const agent = agents[s.name];
                return (
                  <button
                    key={s.name}
                    onClick={() => {
                      setContent((prev) => prev.trimEnd() + ` @${s.name} `);
                      textareaRef.current?.focus();
                    }}
                    className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] transition-all bg-primary/[0.06] text-primary border border-primary/15 hover:bg-primary/[0.12] hover:border-primary/30"
                  >
                    <span className="text-[11px]">{agent?.avatar || "\u{1F916}"}</span>
                    <span className="font-medium">{agent?.display_name || s.name}</span>
                    <span className="text-[8px] opacity-60">&#xB7; {s.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Quick missions -- show when focused and empty */}
        {focused && !hasContent && (
          <div className="mt-3 animate-fade-in">
            <div className="text-[9px] font-bold uppercase tracking-wider mb-2 text-muted-foreground">
              Quick missions
            </div>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_MISSIONS.map((m) => (
                <button
                  key={m.label}
                  onClick={() => applyTemplate(m.template)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-foreground hover:border-border"
                >
                  <span className="text-[10px]">{m.icon}</span>
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2.5 border-t">
        <div className="flex items-center gap-2">
          {/* Realm selector + Flair chips */}
          {hasContent && (
            <div className="flex items-center gap-1 animate-fade-in">
              {REALMS.filter((r) => r.id !== "all").slice(0, 4).map((realm) => (
                <button
                  key={realm.id}
                  onClick={() => setSelectedRealm(selectedRealm === realm.id ? null : realm.id)}
                  className={cn(
                    "flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] transition-all border",
                    selectedRealm === realm.id
                      ? "border-border"
                      : "border-transparent"
                  )}
                  style={{
                    background: selectedRealm === realm.id ? `${realm.color}15` : undefined,
                    color: selectedRealm === realm.id ? realm.color : undefined,
                  }}
                  title={realm.name}
                >
                  <span className="text-[8px]">{realm.icon}</span>
                </button>
              ))}
              <Separator orientation="vertical" className="h-3 mx-0.5" />
              {FLAIRS.slice(0, 5).map((f) => (
                <button
                  key={f.id}
                  onClick={() => setSelectedFlair(selectedFlair === f.id ? null : f.id)}
                  className={cn(
                    "px-1.5 py-0.5 rounded text-[9px] font-medium transition-all border",
                    selectedFlair === f.id
                      ? "border-border"
                      : "border-transparent text-muted-foreground"
                  )}
                  style={{
                    background: selectedFlair === f.id ? `${f.color}15` : undefined,
                    color: selectedFlair === f.id ? f.color : undefined,
                  }}
                  title={f.label}
                >
                  {f.icon}
                </button>
              ))}
            </div>
          )}
          {!hasContent && (
            <span className="text-[11px] data-mono text-muted-foreground">
              <kbd className="px-1 py-0.5 rounded text-[9px] font-mono bg-accent border border-border text-muted-foreground">
                @
              </kbd>
              <span className="ml-1.5">to summon</span>
            </span>
          )}
          {hasContent && (
            <span className="text-[10px] data-mono text-muted-foreground">
              {content.length}<span className="text-border">/2000</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">
            {hasContent ? "\u2318\u21B5" : ""}
          </span>
          <Button
            onClick={handleSubmit}
            disabled={!hasContent}
            size="sm"
            className="px-4 text-[12px] font-semibold"
          >
            Transmit
          </Button>
        </div>
      </div>
    </Card>
  );
});
