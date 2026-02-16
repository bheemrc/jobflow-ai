"use client";

import React, { Suspense, useState, useEffect, useRef, useCallback, useMemo, lazy } from "react";
import { useSearchParams } from "next/navigation";
import { useAppStore, type ChatMessage, type FocusRoom } from "@/lib/store";
import ResumeUpload from "@/components/resume-upload";
import Markdown from "@/components/markdown";
import MessageActionBar from "@/components/chat-actions/message-action-bar";
import AddToPrepModal from "@/components/chat-actions/add-to-prep-modal";
import AssignToBotModal from "@/components/chat-actions/assign-to-bot-modal";
import AssignToNewBotModal from "@/components/chat-actions/assign-to-new-bot-modal";
import {
  Loader2,
  Sparkles,
  Check,
  X,
  ChevronDown,
  Copy,
  FileText,
  Share2,
  AlertCircle,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";

const FlowEditor = lazy(() => import("@/components/flow-editor"));

// Types
interface ToolEvent {
  type: "start" | "end";
  tool: string;
  agent?: string;
  input?: string;
  output?: string;
}

interface ActionButton {
  label: string;
  type: string;
  value: string;
}

interface CoachResponse {
  session_id: string;
  response: string;
  thinking?: string;
  actions: ActionButton[];
  sections_generated: string[];
  section_cards?: SectionCard[];
}

interface SectionCard {
  card_type: string;
  title: string;
  agent: string;
  content: string;
  data?: Record<string, unknown>;
}

interface TriggerEvent {
  trigger_type: string;
  title: string;
  message: string;
  priority: string;
}

const TOOL_ICONS: Record<string, string> = {
  build_strategy: "\u2694\uFE0F",
  research_company: "\uD83C\uDFE2",
  prepare_interview: "\u265F\uFE0F",
  review_resume: "\uD83D\uDCC4",
  extract_resume_profile: "\uD83D\uDD0D",
  search_jobs: "\uD83D\uDD0E",
  search_jobs_for_resume: "\uD83C\uDFAF",
  get_saved_jobs: "\uD83D\uDCCB",
  get_job_pipeline: "\uD83D\uDCCA",
  update_job_stage: "\u27A1\uFE0F",
  get_leetcode_progress: "\uD83D\uDCC8",
  select_leetcode_problems: "\uD83E\uDDE9",
  log_leetcode_attempt_tool: "\u270D\uFE0F",
  web_search: "\uD83C\uDF10",
};

const TOOL_LABELS: Record<string, string> = {
  build_strategy: "Strategist analyzing vectors",
  research_company: "Oracle scanning intel",
  prepare_interview: "Strategist preparing battle plan",
  review_resume: "Forge analyzing resume",
  extract_resume_profile: "Forge profiling skills",
  search_jobs: "Pathfinder scanning opportunities",
  search_jobs_for_resume: "Pathfinder matching targets",
  get_saved_jobs: "Sentinel checking pipeline",
  get_job_pipeline: "Sentinel loading pipeline state",
  update_job_stage: "Sentinel updating stage",
  get_leetcode_progress: "Cipher checking progress",
  select_leetcode_problems: "Cipher selecting challenges",
  log_leetcode_attempt_tool: "Cipher logging attempt",
  web_search: "Oracle searching the web",
};

const AGENT_LABELS: Record<string, string> = {
  coach: "Nexus",
  job_intake: "\u26A1 Pathfinder",
  resume_tailor: "\uD83D\uDD25 Forge",
  recruiter_chat: "\u2726 Catalyst",
  interview_prep: "\u265F\uFE0F Strategist",
  leetcode_coach: "\u25C8 Cipher",
  system_design: "\u25B3 Architect",
  approval_gate: "\u25C6 Sentinel Gate",
  merge: "\u2B21 Nexus Synthesis",
  respond: "\u2B21 Nexus",
};

export default function AIPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      }
    >
      <CoachPage />
    </Suspense>
  );
}

function CoachPage() {
  const searchParams = useSearchParams();

  const resumeId = useAppStore((s) => s.resumeId);
  const setResumeId = useAppStore((s) => s.setResumeId);
  const sessionId = useAppStore((s) => s.coachSessionId);
  const setSessionId = useAppStore((s) => s.setCoachSessionId);
  const mainMessages = useAppStore((s) => s.chatMessages);
  const setMainMessages = useAppStore((s) => s.setChatMessages);
  const clearChat = useAppStore((s) => s.clearChat);

  // Focus rooms
  const rooms = useAppStore((s) => s.rooms);
  const activeRoomId = useAppStore((s) => s.activeRoomId);
  const createRoom = useAppStore((s) => s.createRoom);
  const deleteRoom = useAppStore((s) => s.deleteRoom);
  const setActiveRoom = useAppStore((s) => s.setActiveRoom);
  const setRoomMessages = useAppStore((s) => s.setRoomMessages);

  const isMainRoom = activeRoomId === "main";
  const activeRoom = rooms.find((r) => r.id === activeRoomId);
  const messages = isMainRoom ? mainMessages : (activeRoom?.messages ?? []);
  const currentSessionId = isMainRoom ? sessionId : activeRoomId;

  const setMessages = useCallback(
    (v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      if (isMainRoom) setMainMessages(v);
      else setRoomMessages(activeRoomId, v);
    },
    [isMainRoom, activeRoomId, setMainMessages, setRoomMessages]
  );

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showResumeUpload, setShowResumeUpload] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [showFlowEditor, setShowFlowEditor] = useState(false);
  const [showNewRoomInput, setShowNewRoomInput] = useState(false);
  const [newRoomTopic, setNewRoomTopic] = useState("");
  const [actionModal, setActionModal] = useState<{ type: "prep" | "assign" | "new-bot"; content: string } | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    useAppStore.persist.rehydrate();
    const msgs = useAppStore.getState().chatMessages;
    const cleaned = msgs.filter((m) => !m.isLoading);
    if (cleaned.length !== msgs.length) {
      useAppStore.getState().setChatMessages(cleaned);
    }
  }, []);

  // Silently load existing resume on mount (no chat message)
  useEffect(() => {
    const stored = useAppStore.getState().resumeId;
    if (stored) return; // already have one
    fetch("/api/ai/resumes")
      .then((r) => r.json())
      .then((data) => {
        if (data.resumes?.length) {
          setResumeId(data.resumes[0]);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isNearBottomRef.current) return;
    const container = scrollContainerRef.current;
    if (container) {
      // During streaming use instant scroll to avoid jank from competing smooth scrolls
      if (isLoading) {
        container.scrollTop = container.scrollHeight;
      } else {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages, isLoading]);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const threshold = 150;
    isNearBottomRef.current = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
  }, []);

  useEffect(() => {
    if (initialized) return;
    setInitialized(true);

    const existingMessages = useAppStore.getState().chatMessages;
    if (existingMessages.length > 0) return;

    const company = searchParams.get("company") || undefined;
    const role = searchParams.get("role") || undefined;
    const source = searchParams.get("source") || undefined;
    const jobStatus = searchParams.get("status") || undefined;
    const jobId = searchParams.get("job_id") || undefined;
    // Legacy support: still accept description param if present
    const jobDescriptionParam = searchParams.get("description") || undefined;

    // If coming from saved jobs, auto-send a prep message
    const autoMessage = source === "saved_job" && company && role
      ? `Help me prepare for the ${role} role at ${company}. Analyze the job, tailor my resume, and prep me for the interview.`
      : null;

    const timer = setTimeout(async () => {
      // Fetch job description from API if we have a job_id (clean URL)
      let jobDescription = jobDescriptionParam;
      if (jobId && !jobDescription) {
        try {
          const res = await fetch(`/api/jobs/${jobId}`);
          if (res.ok) {
            const job = await res.json();
            jobDescription = job.description || undefined;
          }
        } catch { /* ignore -- agents can still work without JD */ }
      }

      const currentResumeId = useAppStore.getState().resumeId;
      sendToCoach(autoMessage, {
        resume_id: currentResumeId || undefined,
        company,
        role,
        source,
        job_status: jobStatus,
        job_description: jobDescription,
      });
    }, 100);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized]);

  /** Resolve which room to target -- allows explicit override for fork flow. */
  function resolveRoom(targetRoomId?: string) {
    const rid = targetRoomId ?? useAppStore.getState().activeRoomId;
    const isMain = rid === "main";
    const room = isMain ? undefined : useAppStore.getState().rooms.find((r) => r.id === rid);
    const sid = isMain ? useAppStore.getState().coachSessionId : rid;
    const updateMsgs = (v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      if (isMain) setMainMessages(v);
      else setRoomMessages(rid, v);
    };
    return { isMain, room, sessionId: sid, updateMsgs };
  }

  async function sendToCoach(
    message: string | null,
    context?: Record<string, string | number | undefined>,
    targetRoomId?: string,
  ) {
    const target = resolveRoom(targetRoomId);
    setIsLoading(true);

    if (message) {
      target.updateMsgs((prev) => [...prev, { role: "user", content: message }]);
    }

    target.updateMsgs((prev) => [
      ...prev,
      { role: "assistant", content: "", isLoading: true },
    ]);

    const body: Record<string, unknown> = {};
    if (message) body.message = message;
    if (target.sessionId) body.session_id = target.sessionId;
    if (context) {
      body.context = context;
    }
    // Add focus_topic for focus rooms
    if (!target.isMain && target.room?.topic) {
      body.context = { ...(body.context as Record<string, unknown> || {}), focus_topic: target.room.topic };
    }

    try {
      await sendToCoachStream(body, target.updateMsgs, target.isMain);
    } catch {
      try {
        await sendToCoachFallback(body, target.updateMsgs, target.isMain);
      } catch (err) {
        target.updateMsgs((prev) => {
          const updated = prev.filter((m) => !m.isLoading);
          return [
            ...updated,
            {
              role: "assistant",
              content:
                err instanceof Error
                  ? `I couldn't connect to the AI service. ${err.message}`
                  : "Failed to reach the AI service. Make sure the backend is running.",
            },
          ];
        });
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function sendToCoachStream(
    body: Record<string, unknown>,
    targetSetMessages?: (v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void,
    targetIsMain?: boolean,
  ) {
    const updateMsgs = targetSetMessages ?? setMessages;
    const shouldSetSessionId = targetIsMain ?? isMainRoom;
    const res = await fetch("/api/ai/coach/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) throw new Error(`Stream error (${res.status})`);

    const contentType = res.headers.get("Content-Type") || "";
    if (!contentType.includes("text/event-stream")) throw new Error("Not an SSE response");

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();

    // -- Mutable refs for streaming state (no React re-renders) --
    let toolsActive: string[] = [];
    let toolsCompleted: string[] = [];
    let toolEvents: ChatMessage["toolEvents"] = [];
    let agentEvents: ChatMessage["agentEvents"] = [];
    let sectionCards: SectionCard[] = [];
    let buffer = "";
    let streamedText = "";
    const agentStreams: Record<string, string> = {};
    let dirty = false;       // flag: new data since last flush
    let rafId = 0;           // requestAnimationFrame handle

    // -- Batched flush: updates React state at most once per frame --
    const flushToReact = () => {
      rafId = 0;
      if (!dirty) return;
      dirty = false;
      const displayText = streamedText
        .replace(/\[ROUTE:[^\]]*\]/g, "")
        .replace(/\[COMPANY:\s*[^\]]+\]/g, "")
        .replace(/\[ROLE:\s*[^\]]+\]/g, "");
      const snapshot = {
        content: displayText,
        toolProgress: { active: [...toolsActive], completed: [...toolsCompleted] },
        toolEvents: toolEvents ? [...toolEvents] : [],
        agentEvents: agentEvents ? [...agentEvents] : [],
        agentStreams: { ...agentStreams },
      };
      updateMsgs((prev) => {
        const idx = [...prev].reverse().findIndex((m) => m.role === "assistant" && m.isLoading);
        if (idx === -1) {
          return [...prev, { role: "assistant", ...snapshot, isLoading: true }];
        }
        const realIdx = prev.length - 1 - idx;
        const next = [...prev];
        next[realIdx] = { ...next[realIdx], ...snapshot, isLoading: true };
        return next;
      });
    };

    const scheduleFlush = () => {
      dirty = true;
      if (!rafId) rafId = requestAnimationFrame(flushToReact);
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event: Record<string, unknown>;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }

        if (event.type === "delta") {
          streamedText += (event.text as string) || "";
          scheduleFlush();
        }

        if (event.type === "agent_delta") {
          const agent = event.agent as string;
          agentStreams[agent] = (agentStreams[agent] || "") + ((event.text as string) || "");
          scheduleFlush();
        }

        if (event.type === "agent_start") {
          agentEvents = [...(agentEvents || []), { agent: event.agent as string, status: "start" }];
          scheduleFlush();
        }

        if (event.type === "agent_end") {
          agentEvents = [...(agentEvents || []), { agent: event.agent as string, status: "end" }];
          scheduleFlush();
        }

        if (event.type === "tool_start") {
          const toolName = event.tool as string;
          const agentName = (event.agent as string) || undefined;
          const input = typeof event.input === "string" ? event.input : event.input ? JSON.stringify(event.input) : undefined;
          toolsActive = [...toolsActive, toolName];
          toolEvents = [...(toolEvents || []), { type: "start", tool: toolName, agent: agentName, input }];
          scheduleFlush();
        }

        if (event.type === "tool_end") {
          const toolName = event.tool as string;
          const agentName = (event.agent as string) || undefined;
          const output = typeof event.output === "string" ? (event.output as string) : undefined;
          toolsActive = toolsActive.filter((t) => t !== toolName);
          toolsCompleted = [...toolsCompleted, toolName];
          toolEvents = [...(toolEvents || []), { type: "end", tool: toolName, agent: agentName, output }];
          scheduleFlush();
        }

        if (event.type === "section_card") {
          sectionCards = [...sectionCards, event as unknown as SectionCard];
        }

        if (event.type === "trigger") {
          const trigger = event as unknown as TriggerEvent & { type: string };
          if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
          flushToReact();
          updateMsgs((prev) => [
            ...prev.filter((m) => !m.isLoading),
            {
              role: "assistant",
              content: `**${trigger.title}**: ${trigger.message}`,
              isLoading: false,
            },
            { role: "assistant", content: "", isLoading: true },
          ]);
        }

        if (event.type === "approval_needed" || event.type === "approval_requested") {
          const item = event.type === "approval_requested"
            ? { approval_id: (event.approval_id as number) || undefined, type: (event.approval as Record<string, string>)?.type || "", title: (event.approval as Record<string, string>)?.title || "", agent: (event.agent as string) || "", content: (event.approval as Record<string, string>)?.content || "", priority: (event.approval as Record<string, string>)?.priority || "medium" }
            : event.item as ChatMessage["approvalNeeded"];
          updateMsgs((prev) => {
            const idx = [...prev].reverse().findIndex((m) => m.role === "assistant" && m.isLoading);
            if (idx === -1) return prev;
            const realIdx = prev.length - 1 - idx;
            const next = [...prev];
            next[realIdx] = { ...next[realIdx], approvalNeeded: item };
            return next;
          });
        }

        if (event.type === "response") {
          // Cancel any pending frame flush -- we're doing the final update
          if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
          dirty = false; // prevent trailing flushToReact from overwriting with isLoading: true
          const data = event as unknown as CoachResponse & { type: string };
          if (data.session_id && shouldSetSessionId) setSessionId(data.session_id as string);

          const cleanedStreamedText = streamedText
            .replace(/\s*```thinking\s*\n[\s\S]*?```\s*/g, "")
            .replace(/\s*```actions\s*\n[\s\S]*?```\s*/g, "")
            .replace(/\[ROUTE:[^\]]*\]/g, "")
            .replace(/\[COMPANY:\s*[^\]]+\]/g, "")
            .replace(/\[ROLE:\s*[^\]]+\]/g, "")
            .trim();
          const finalContent = cleanedStreamedText.length > (data.response?.length || 0) ? cleanedStreamedText : data.response;

          updateMsgs((prev) => {
            const idx = [...prev].reverse().findIndex((m) => m.role === "assistant" && m.isLoading);
            if (idx === -1) {
              return [...prev, { role: "assistant", content: finalContent, actions: data.actions, sections: data.sections_generated }];
            }
            const realIdx = prev.length - 1 - idx;
            const next = [...prev];
            next[realIdx] = { ...next[realIdx], content: finalContent, actions: data.actions, sections: data.sections_generated, sectionCards: sectionCards.length > 0 ? sectionCards : (data.section_cards || undefined), isLoading: false, toolEvents: toolEvents ? [...toolEvents] : [], agentEvents: agentEvents ? [...agentEvents] : [], agentStreams: Object.keys(agentStreams).length > 0 ? { ...agentStreams } : undefined };
            return next;
          });
        }

        if (event.type === "error") {
          if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
          dirty = false;
          updateMsgs((prev) => {
            const updated = prev.filter((m) => !m.isLoading);
            return [...updated, { role: "assistant", content: `Error: ${event.message || "Unknown error"}` }];
          });
        }
      }
    }

    // Flush any remaining batched updates after stream ends
    if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
    if (dirty) flushToReact();
  }

  async function sendToCoachFallback(
    body: Record<string, unknown>,
    targetSetMessages?: (v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void,
    targetIsMain?: boolean,
  ) {
    const updateMsgs = targetSetMessages ?? setMessages;
    const shouldSetSessionId = targetIsMain ?? isMainRoom;
    const res = await fetch("/api/ai/coach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || `Service error (${res.status})`);
    }

    const data: CoachResponse = await res.json();
    if (data.session_id && shouldSetSessionId) setSessionId(data.session_id);

    updateMsgs((prev) => {
      const updated = prev.filter((m) => !m.isLoading);
      return [...updated, { role: "assistant", content: data.response, thinking: data.thinking, actions: data.actions, sections: data.sections_generated }];
    });
  }

  function handleSend() {
    if (!input.trim() || isLoading) return;
    const text = input.trim();
    setInput("");
    // Always include resume_id so agents can access the resume
    const currentResumeId = useAppStore.getState().resumeId;
    sendToCoach(text, currentResumeId ? { resume_id: currentResumeId } : undefined);
    inputRef.current?.focus();
  }

  const handleAction = useCallback((action: ActionButton) => {
    if (action.type === "upload_resume") {
      setMessages((prev) => [...prev, { role: "assistant", content: "", showUpload: true }]);
      return;
    }
    const text = action.value ? `${action.label}: ${action.value}` : action.label;
    sendToCoach(text);
    inputRef.current?.focus();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setMessages]);

  const handleFork = useCallback((content: string, suggestedTopic: string) => {
    const roomId = createRoom(suggestedTopic);
    if (!roomId) return;
    setTimeout(() => {
      const currentResumeId = useAppStore.getState().resumeId;
      sendToCoach(
        `Continue working on: ${suggestedTopic}\n\nContext:\n${content.slice(0, 3000)}`,
        {
          resume_id: currentResumeId || undefined,
          focus_topic: suggestedTopic,
        },
        roomId,
      );
    }, 100);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createRoom]);

  function handleCreateRoom() {
    const topic = newRoomTopic.trim();
    if (!topic) return;
    setNewRoomTopic("");
    setShowNewRoomInput(false);
    createRoom(topic);
  }

  const handleOpenPrep = useCallback((content: string) => setActionModal({ type: "prep", content }), []);
  const handleOpenAssign = useCallback((content: string) => setActionModal({ type: "assign", content }), []);
  const handleOpenNewBot = useCallback((content: string) => setActionModal({ type: "new-bot", content }), []);

  function handleResumeUploaded(id: string) {
    const prev = useAppStore.getState().resumeId;
    if (id === prev) return;
    setResumeId(id);
    // Only send a chat message when the user actively uploaded via the panel
    if (showResumeUpload) {
      setShowResumeUpload(false);
      sendToCoach("I just uploaded my resume.", { resume_id: id });
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex h-full max-h-screen bg-background">
    <div className={cn("flex flex-col min-w-0 overflow-hidden", showFlowEditor ? "w-1/2" : "w-full")}>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-blue-500 shadow-sm">
            <span className="text-sm text-primary-foreground brightness-200">{"\u2B21"}</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground">AI Career Coach</h1>
            <p className="text-[10px] font-mono text-muted-foreground/70">
              Your AI-powered career assistant
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFlowEditor(!showFlowEditor)}
            className={cn(
              "rounded-lg px-2.5 py-1.5 text-[10px] font-semibold h-auto",
              showFlowEditor && "text-primary border-primary/30"
            )}
          >
            Edit Flows
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowResumeUpload(!showResumeUpload)}
            className="rounded-lg px-2.5 py-1.5 text-[10px] font-semibold h-auto gap-1.5"
          >
            {resumeId && (
              <FileText className="h-3 w-3 text-success" />
            )}
            {resumeId ? "Change Resume" : "Upload Resume"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { clearChat(); setInitialized(false); }}
            className="rounded-lg px-2.5 py-1.5 text-[10px] font-semibold h-auto"
          >
            New Chat
          </Button>
        </div>
      </div>

      {/* Room Tab Bar */}
      {rooms.length > 0 && (
        <div className="flex items-center gap-1 px-4 py-1.5 overflow-x-auto border-b bg-card">
          <button
            onClick={() => setActiveRoom("main")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium whitespace-nowrap transition-colors",
              isMainRoom
                ? "bg-primary/10 text-primary border-b-2 border-primary"
                : "text-muted-foreground border-b-2 border-transparent"
            )}
          >
            {"\u2B21"} Main
          </button>
          {rooms.map((room) => (
            <div key={room.id} className="flex items-center">
              <button
                onClick={() => setActiveRoom(room.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium whitespace-nowrap transition-colors",
                  activeRoomId === room.id
                    ? "bg-primary/10 text-primary border-b-2 border-primary"
                    : "text-muted-foreground border-b-2 border-transparent"
                )}
              >
                {room.topic.length > 20 ? room.topic.slice(0, 20) + "..." : room.topic}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); deleteRoom(room.id); }}
                className="ml-0.5 rounded p-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent"
                title="Close room"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
          {rooms.length < 5 && (
            showNewRoomInput ? (
              <form
                onSubmit={(e) => { e.preventDefault(); handleCreateRoom(); }}
                className="flex items-center gap-1 ml-1"
              >
                <Input
                  autoFocus
                  value={newRoomTopic}
                  onChange={(e) => setNewRoomTopic(e.target.value)}
                  onBlur={() => { if (!newRoomTopic.trim()) setShowNewRoomInput(false); }}
                  onKeyDown={(e) => { if (e.key === "Escape") { setShowNewRoomInput(false); setNewRoomTopic(""); } }}
                  placeholder="Topic name..."
                  className="rounded-md px-2 py-1 text-[11px] w-32 h-auto"
                />
                <button type="submit" className="text-[11px] font-medium text-primary">
                  Add
                </button>
              </form>
            ) : (
              <button
                onClick={() => setShowNewRoomInput(true)}
                className="flex items-center justify-center rounded-lg px-2 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent"
                title="New focus room"
              >
                <Plus className="h-3 w-3" />
              </button>
            )
          )}
        </div>
      )}

      {/* Resume upload inline panel */}
      {showResumeUpload && (
        <div className="px-6 py-4 border-b bg-card">
          <div className="mx-auto max-w-md">
            <ResumeUpload onResumeId={handleResumeUploaded} replaceMode />
          </div>
        </div>
      )}

      {/* Chat messages */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.map((msg, i) => (
            <ChatMessageRow
              key={`${msg.role}-${i}`}
              msg={msg}
              isLoading={isLoading}
              currentSessionId={currentSessionId}
              setMessages={setMessages}
              handleAction={handleAction}
              handleFork={handleFork}
              handleResumeUploaded={handleResumeUploaded}
              onAddToPrep={handleOpenPrep}
              onAssignToBot={handleOpenAssign}
              onNewBot={handleOpenNewBot}
            />
          ))}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t bg-background">
        <form
          onSubmit={(e) => { e.preventDefault(); handleSend(); }}
          className="mx-auto flex max-w-3xl gap-3 items-end"
        >
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              // Auto-resize up to 4 lines
              const el = e.target;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 96) + "px";
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={resumeId ? "Ask anything about your job search, resume, or interviews..." : "Upload your resume to get started, or ask a question..."}
            className="flex-1 rounded-xl px-4 py-3 text-sm resize-none min-h-[44px] max-h-[96px]"
            rows={1}
            disabled={isLoading}
          />
          <Button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="rounded-xl px-5 py-3 text-sm"
          >
            Send
          </Button>
        </form>
      </div>
    </div>

    {/* Chat Action Modals */}
    {actionModal?.type === "prep" && (
      <AddToPrepModal
        content={actionModal.content}
        onClose={() => setActionModal(null)}
      />
    )}
    {actionModal?.type === "assign" && (
      <AssignToBotModal
        content={actionModal.content}
        onClose={() => setActionModal(null)}
      />
    )}
    {actionModal?.type === "new-bot" && (
      <AssignToNewBotModal
        content={actionModal.content}
        onClose={() => setActionModal(null)}
      />
    )}

    {/* Flow Editor Panel */}
    {showFlowEditor && (
      <div className="w-1/2 flex flex-col border-l min-w-0">
        <Suspense
          fallback={
            <div className="flex flex-1 items-center justify-center bg-card">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
            </div>
          }
        >
          <FlowEditor onClose={() => setShowFlowEditor(false)} />
        </Suspense>
      </div>
    )}
    </div>
  );
}

// --------------------------------------------------------------
//  THROTTLED VALUE HOOK (for streaming markdown)
// --------------------------------------------------------------

function useThrottledValue<T>(value: T, delay: number): T {
  const [throttled, setThrottled] = useState(value);
  const lastUpdate = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const now = Date.now();
    if (now - lastUpdate.current >= delay) {
      lastUpdate.current = now;
      setThrottled(value);
    } else {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        lastUpdate.current = Date.now();
        setThrottled(value);
      }, delay - (now - lastUpdate.current));
    }
    return () => clearTimeout(timer.current);
  }, [value, delay]);

  return throttled;
}

// --------------------------------------------------------------
//  STREAMING MARKDOWN (throttled to ~200ms during streaming)
// --------------------------------------------------------------

function StreamingMarkdown({ content }: { content: string }) {
  const throttled = useThrottledValue(content, 200);
  return <Markdown>{throttled}</Markdown>;
}

// --------------------------------------------------------------
//  LOADING AGENT MAP (memoized helper)
// --------------------------------------------------------------

const LoadingAgentProgress = React.memo(function LoadingAgentProgress({
  agentEvents,
}: {
  agentEvents: NonNullable<ChatMessage["agentEvents"]>;
}) {
  const visibleAgents = useMemo(() => {
    const agentMap = new Map<string, "start" | "end">();
    for (const evt of agentEvents) agentMap.set(evt.agent, evt.status);
    return Array.from(agentMap.entries()).filter(
      ([agent]) => agent !== "coach" && agent !== "respond" && agent !== "merge" && agent !== "approval_gate"
    );
  }, [agentEvents]);

  if (visibleAgents.length === 0) return null;

  return (
    <div className="space-y-1">
      {visibleAgents.map(([agent, status]) => (
        <div key={agent} className="flex items-center gap-2 text-[12px]">
          {status === "end" ? (
            <Check className="h-3.5 w-3.5 shrink-0 text-success" />
          ) : (
            <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0 text-primary" />
          )}
          <span className={status === "end" ? "text-success" : "text-muted-foreground"}>
            {AGENT_LABELS[agent] || agent}{status === "start" ? "..." : ""}
          </span>
        </div>
      ))}
    </div>
  );
});

// --------------------------------------------------------------
//  CHAT MESSAGE ROW (memoized)
// --------------------------------------------------------------

const ChatMessageRow = React.memo(function ChatMessageRow({
  msg,
  isLoading,
  currentSessionId,
  setMessages,
  handleAction,
  handleFork,
  handleResumeUploaded,
  onAddToPrep,
  onAssignToBot,
  onNewBot,
}: {
  msg: ChatMessage;
  isLoading: boolean;
  currentSessionId: string | null;
  setMessages: (v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  handleAction: (action: ActionButton) => void;
  handleFork: (content: string, suggestedTopic: string) => void;
  handleResumeUploaded: (id: string) => void;
  onAddToPrep: (content: string) => void;
  onAssignToBot: (content: string) => void;
  onNewBot: (content: string) => void;
}) {
  return (
    <div className={cn("chat-message flex gap-3 animate-fade-in-up", msg.role === "user" ? "justify-end" : "justify-start")}>
      {msg.role === "assistant" && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg mt-0.5 bg-gradient-to-br from-primary to-blue-500">
          {msg.isLoading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary-foreground" />
          ) : (
            <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
          )}
        </div>
      )}

      <div className={cn("max-w-[80%]", msg.role === "user" ? "" : "flex-1 max-w-none")}>
        {msg.isLoading ? (
          <Card className="p-4 space-y-3">
            <div className="relative z-10">
              {/* Agent progress */}
              {msg.agentEvents && msg.agentEvents.length > 0 && (
                <LoadingAgentProgress agentEvents={msg.agentEvents} />
              )}
              {/* Tool progress -- grouped by agent when parallel */}
              {msg.toolEvents && msg.toolEvents.length > 0 && (
                <ToolProgressGrouped toolEvents={msg.toolEvents} />
              )}
              {/* Live per-agent streaming preview */}
              {msg.agentStreams && Object.keys(msg.agentStreams).length > 0 && msg.agentEvents && (
                <AgentStreamPreview agentStreams={msg.agentStreams} agentEvents={msg.agentEvents} isLoading />
              )}
              {msg.content ? (
                <div className="prose-sm max-w-none text-sm leading-relaxed text-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                  <StreamingMarkdown content={msg.content} />
                </div>
              ) : !msg.toolEvents?.length && !msg.agentEvents?.length ? (
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:0ms]" />
                    <div className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:150ms]" />
                    <div className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:300ms]" />
                  </div>
                  <span className="text-[12px] text-muted-foreground/70">Thinking...</span>
                </div>
              ) : null}
            </div>
          </Card>
        ) : msg.showUpload ? (
          <Card className="p-5">
            <div className="relative z-10">
              <ResumeUpload onResumeId={handleResumeUploaded} />
            </div>
          </Card>
        ) : msg.role === "user" ? (
          <div className="rounded-2xl rounded-br-md px-4 py-3 text-sm bg-gradient-to-br from-primary to-blue-500 text-primary-foreground">
            <span className="whitespace-pre-wrap font-medium">{msg.content}</span>
          </div>
        ) : (
          <div className="space-y-3">
            {msg.thinking && (
              <details className="text-[12px] text-muted-foreground/70">
                <summary className="cursor-pointer text-muted-foreground/70">Thinking...</summary>
                <p className="mt-1 pl-3 border-l-2 border-border">{msg.thinking}</p>
              </details>
            )}
            {/* Agent activity -- collapsed summary on completed messages */}
            {msg.agentEvents && msg.agentEvents.length > 0 && (
              <CompletedAgentSummary agentEvents={msg.agentEvents} toolEvents={msg.toolEvents} />
            )}
            {msg.approvalNeeded && (
              <ApprovalInlineCard
                approval={msg.approvalNeeded}
                sessionId={currentSessionId || ""}
                onResolved={() => {
                  // Mark approval as handled in the message
                  setMessages((prev) => {
                    const next = [...prev];
                    const idx = next.indexOf(msg);
                    if (idx >= 0) {
                      next[idx] = { ...next[idx], approvalNeeded: undefined };
                    }
                    return next;
                  });
                }}
              />
            )}
            {msg.content.trim() && <AssistantMessage content={msg.content} />}
            {/* Section Cards */}
            {msg.sectionCards && msg.sectionCards.length > 0 && (
              <div className="space-y-3">
                {msg.sectionCards.map((card, idx) => (
                  <SectionCardInline
                    key={idx}
                    card={card}
                    onFork={handleFork}
                    onAddToPrep={onAddToPrep}
                    onAssignToBot={onAssignToBot}
                    onNewBot={onNewBot}
                  />
                ))}
              </div>
            )}
            {msg.actions && msg.actions.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {msg.actions.map((action, j) => (
                  <Button
                    key={j}
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction(action)}
                    disabled={isLoading}
                    className="rounded-lg px-3 py-1.5 text-[12px] font-semibold h-auto text-primary border-primary/30"
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            )}
            {/* Fork into focus room + message actions */}
            {(() => {
              const fullContent = [
                msg.content,
                ...(msg.sectionCards || []).map((c: SectionCard) => c.content),
              ].filter(Boolean).join("\n\n");
              const hasContent = fullContent.length > 50;
              if (!hasContent || msg.isLoading) return null;
              return (
                <div className="flex items-center gap-1 flex-wrap">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleFork(fullContent, fullContent.slice(0, 60).replace(/[#*_\n]/g, "").trim())}
                    className="h-auto gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
                    title="Fork into Focus Room"
                  >
                    <Share2 className="h-3 w-3" />
                    Focus
                  </Button>
                  <MessageActionBar
                    content={fullContent}
                    onAddToPrep={() => onAddToPrep(fullContent)}
                    onAssignToBot={() => onAssignToBot(fullContent)}
                    onNewBot={() => onNewBot(fullContent)}
                  />
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
});

// --------------------------------------------------------------
//  TOOL PROGRESS -- GROUPED BY AGENT
// --------------------------------------------------------------

const ToolProgressGrouped = React.memo(function ToolProgressGrouped({ toolEvents }: { toolEvents: ToolEvent[] }) {
  // Group tools by agent
  const agentGroups = new Map<string, ToolEvent[]>();
  for (const evt of toolEvents) {
    const key = evt.agent || "_ungrouped";
    const group = agentGroups.get(key) || [];
    group.push(evt);
    agentGroups.set(key, group);
  }

  // Deduplicate tools within each group (keep end events over start)
  function dedup(events: ToolEvent[]): ToolEvent[] {
    const toolMap = new Map<string, ToolEvent>();
    for (const evt of events) {
      const existing = toolMap.get(evt.tool);
      if (evt.type === "end") {
        toolMap.set(evt.tool, { ...evt, input: existing?.input || evt.input });
      } else if (!existing) {
        toolMap.set(evt.tool, evt);
      }
    }
    return Array.from(toolMap.values());
  }

  const hasMultipleAgents = agentGroups.size > 1 || (agentGroups.size === 1 && !agentGroups.has("_ungrouped"));

  if (!hasMultipleAgents) {
    // Single agent or no agent info -- flat list
    return (
      <div className="space-y-1.5">
        {dedup(toolEvents).map((evt, idx) => (
          <ToolCallBlock key={`${evt.tool}-${idx}`} evt={evt} />
        ))}
      </div>
    );
  }

  // Multiple agents -- group under agent headers
  return (
    <div className="space-y-3">
      {Array.from(agentGroups.entries()).map(([agent, events]) => (
        <div key={agent} className="space-y-1">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-muted-foreground/70">
            <Separator className="flex-1" />
            <span>{AGENT_LABELS[agent] || agent}</span>
            <Separator className="flex-1" />
          </div>
          <div className="space-y-1 pl-1">
            {dedup(events).map((evt, idx) => (
              <ToolCallBlock key={`${agent}-${evt.tool}-${idx}`} evt={evt} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
});

function formatToolContent(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      className="px-1.5 py-0.5 rounded text-[10px] font-medium cursor-pointer transition-colors bg-background text-muted-foreground hover:text-foreground"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function ToolCallBlock({ evt }: { evt: ToolEvent }) {
  const [showInput, setShowInput] = useState(false);
  const [showOutput, setShowOutput] = useState(false);
  const isDone = evt.type === "end";
  const icon = TOOL_ICONS[evt.tool] || "\u2699\uFE0F";
  const label = TOOL_LABELS[evt.tool] || evt.tool;

  return (
    <div className="rounded-lg overflow-hidden text-[12px] border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 px-2.5 py-1.5">
        {isDone ? (
          <Check className="h-3.5 w-3.5 shrink-0 text-success" />
        ) : (
          <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0 text-primary" />
        )}
        <span className="shrink-0">{icon}</span>
        <span className={cn("font-medium truncate", isDone ? "text-foreground" : "text-muted-foreground")}>
          {label}{!isDone ? "..." : ""}
        </span>
        {evt.agent && (
          <Badge variant="info" className="ml-auto text-[10px] shrink-0">
            via {AGENT_LABELS[evt.agent] || evt.agent}
          </Badge>
        )}
      </div>

      {/* Toggle buttons */}
      {(evt.input || (isDone && evt.output)) && (
        <div className="flex items-center gap-1.5 px-2.5 pb-1.5">
          {evt.input && (
            <button
              onClick={() => setShowInput((v) => !v)}
              className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-medium cursor-pointer transition-colors",
                showInput ? "bg-primary/15 text-primary" : "bg-background text-muted-foreground"
              )}
            >
              Input {showInput ? "\u25B4" : "\u25BE"}
            </button>
          )}
          {isDone && evt.output && (
            <button
              onClick={() => setShowOutput((v) => !v)}
              className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-medium cursor-pointer transition-colors",
                showOutput ? "bg-success/15 text-success" : "bg-background text-muted-foreground"
              )}
            >
              Output {showOutput ? "\u25B4" : "\u25BE"}
            </button>
          )}
        </div>
      )}

      {/* Input panel */}
      {showInput && evt.input && (
        <div className="border-t bg-primary/[0.04]">
          <div className="flex items-center justify-between px-2.5 pt-1.5">
            <span className="text-[10px] font-semibold text-primary">INPUT</span>
            <CopyButton text={evt.input} />
          </div>
          <pre className="px-2.5 pb-2 pt-1 max-h-48 overflow-auto text-[11px] whitespace-pre-wrap break-words leading-relaxed text-muted-foreground/70 m-0 bg-transparent">
            {formatToolContent(evt.input)}
          </pre>
        </div>
      )}

      {/* Output panel */}
      {showOutput && isDone && evt.output && (
        <div className="border-t bg-success/[0.04]">
          <div className="flex items-center justify-between px-2.5 pt-1.5">
            <span className="text-[10px] font-semibold text-success">
              OUTPUT{evt.output.length > 200 ? ` (${Math.round(evt.output.length / 1024)}KB)` : ""}
            </span>
            <CopyButton text={evt.output} />
          </div>
          <pre className="px-2.5 pb-2 pt-1 max-h-48 overflow-auto text-[11px] whitespace-pre-wrap break-words leading-relaxed text-muted-foreground/70 m-0 bg-transparent">
            {formatToolContent(evt.output)}
          </pre>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------
//  ASSISTANT MESSAGE
// --------------------------------------------------------------

function AssistantMessage({ content }: { content: string }) {
  const sections = parseSections(content);

  if (sections.length === 1 && !sections[0].type) {
    return (
      <Card className="p-5">
        <div className="relative z-10 prose-sm max-w-none text-sm leading-relaxed text-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
          <Markdown>{content}</Markdown>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {sections.map((section, i) =>
        section.type ? (
          <CollapsibleSection key={i} type={section.type} content={section.content} />
        ) : section.content.trim() ? (
          <Card key={i} className="p-5">
            <div className="relative z-10 prose-sm max-w-none text-sm leading-relaxed text-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
              <Markdown>{section.content}</Markdown>
            </div>
          </Card>
        ) : null
      )}
    </div>
  );
}

interface ParsedSection { type: string | null; content: string; }

function parseSections(text: string): ParsedSection[] {
  const sectionPattern = /<!-- section:(\w+) -->/g;
  const sections: ParsedSection[] = [];
  let lastIndex = 0;
  let match;

  while ((match = sectionPattern.exec(text)) !== null) {
    const before = text.slice(lastIndex, match.index).trim();
    if (before) sections.push({ type: null, content: before });
    lastIndex = match.index + match[0].length;
    const nextMatch = sectionPattern.exec(text);
    const endIndex = nextMatch ? nextMatch.index : text.length;
    const sectionContent = text.slice(lastIndex, endIndex).trim();
    sections.push({ type: match[1], content: sectionContent });
    if (nextMatch) sectionPattern.lastIndex = nextMatch.index;
    lastIndex = endIndex;
  }

  const remaining = text.slice(lastIndex).trim();
  if (remaining) sections.push({ type: null, content: remaining });
  if (sections.length === 0) sections.push({ type: null, content: text });
  return sections;
}

const SECTION_LABELS: Record<string, string> = {
  strategy: "Job Search Strategy",
  research: "Company Research",
  interview_prep: "Interview Preparation",
  job_analysis: "Job Analysis",
  resume_diff: "Resume Changes",
  recruiter_draft: "Recruiter Draft",
  leetcode: "LeetCode Coach",
  match_score: "Match Score",
  skill_gap: "Skill Gap Analysis",
  prep_plan: "Prep Plan",
  daily_problems: "Daily Problems",
  mastery_update: "Mastery Update",
  system_design: "System Design",
};

const SECTION_BADGE_VARIANT: Record<string, "info" | "warning" | "success" | "secondary" | "destructive"> = {
  strategy: "info",
  research: "warning",
  interview_prep: "success",
  prep_plan: "success",
  job_analysis: "info",
  match_score: "info",
  skill_gap: "warning",
  resume_diff: "secondary",
  recruiter_draft: "secondary",
  leetcode: "warning",
  daily_problems: "warning",
  mastery_update: "warning",
  system_design: "info",
};

const SECTION_BORDER_COLORS: Record<string, string> = {
  strategy: "border-primary/20",
  research: "border-warning/20",
  interview_prep: "border-success/20",
  prep_plan: "border-success/20",
  job_analysis: "border-blue-400/20",
  match_score: "border-blue-400/20",
  skill_gap: "border-warning/20",
  resume_diff: "border-purple-400/20",
  recruiter_draft: "border-pink-400/20",
  leetcode: "border-orange-400/20",
  daily_problems: "border-orange-400/20",
  mastery_update: "border-orange-400/20",
  system_design: "border-cyan-400/20",
};

function CollapsibleSection({ type, content }: { type: string; content: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);

  const label = SECTION_LABELS[type] || type;
  const badgeVariant = SECTION_BADGE_VARIANT[type] || "info";
  const borderColor = SECTION_BORDER_COLORS[type] || "border-primary/20";

  function handleCopy() {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={cn("rounded-2xl overflow-hidden border", borderColor)}>
      <div className="flex items-center justify-between px-5 py-3">
        <Badge variant={badgeVariant}>
          {label}
        </Badge>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
          >
            {copied ? "Copied!" : "Copy"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
          >
            {collapsed ? "Expand" : "Collapse"}
          </Button>
        </div>
      </div>

      {!collapsed && (
        <div className="px-5 py-4 border-t">
          <div className="prose-sm max-w-none text-sm leading-relaxed text-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <Markdown>{content}</Markdown>
          </div>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------
//  SECTION CARD (rich inline card from backend section_cards)
// --------------------------------------------------------------

const CARD_AGENT_LABELS: Record<string, string> = {
  job_intake: "Job Intake",
  resume_tailor: "Resume Tailor",
  interview_prep: "Interview Prep",
  leetcode_coach: "LeetCode Coach",
  recruiter_chat: "Recruiter Chat",
  system_design: "System Design",
};

function SectionCardInline({ card, onFork, onAddToPrep, onAssignToBot, onNewBot }: { card: SectionCard; onFork?: (content: string, topic: string) => void; onAddToPrep?: (content: string) => void; onAssignToBot?: (content: string) => void; onNewBot?: (content: string) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);

  const label = SECTION_LABELS[card.card_type] || card.title;
  const badgeVariant = SECTION_BADGE_VARIANT[card.card_type] || "info";
  const borderColor = SECTION_BORDER_COLORS[card.card_type] || "border-primary/20";
  const agentLabel = CARD_AGENT_LABELS[card.agent] || card.agent;

  const matchScore = card.data?.score as number | undefined;

  function handleCopy() {
    navigator.clipboard.writeText(card.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={cn("rounded-2xl overflow-hidden animate-fade-in-up border", borderColor)}>
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-2">
          <Badge variant={badgeVariant}>
            {label}
          </Badge>
          <span className="text-[10px] text-muted-foreground/70">
            via {agentLabel}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {matchScore !== undefined && (
            <span className={cn(
              "font-mono text-sm font-bold mr-2",
              matchScore >= 70 ? "text-success" : matchScore >= 40 ? "text-warning" : "text-destructive"
            )}>
              {matchScore}/100
            </span>
          )}
          {onFork && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onFork(card.content, card.title)}
              className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-primary"
              title="Open in a Focus Room"
            >
              Focus
            </Button>
          )}
          {onAddToPrep && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAddToPrep(card.content)}
              className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
              title="Save as prep material"
            >
              Prep
            </Button>
          )}
          {onAssignToBot && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAssignToBot(card.content)}
              className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
              title="Assign to an existing bot"
            >
              Assign
            </Button>
          )}
          {onNewBot && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNewBot(card.content)}
              className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
              title="Create a new bot from this"
            >
              New Bot
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
          >
            {copied ? "Copied!" : "Copy"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="h-auto rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
          >
            {collapsed ? "Expand" : "Collapse"}
          </Button>
        </div>
      </div>

      {!collapsed && card.content && (
        <div className="px-5 py-4 border-t">
          <div className="prose-sm max-w-none text-sm leading-relaxed text-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <Markdown>{card.content}</Markdown>
          </div>
        </div>
      )}
    </div>
  );
}

/* -- Inline Approval Card -- */

function ApprovalInlineCard({
  approval,
  sessionId,
  onResolved,
}: {
  approval: NonNullable<ChatMessage["approvalNeeded"]>;
  sessionId: string;
  onResolved: () => void;
}) {
  const [status, setStatus] = useState<"pending" | "approving" | "rejecting" | "approved" | "rejected">("pending");
  const [error, setError] = useState<string | null>(null);

  const handleDecision = async (decision: "approved" | "rejected") => {
    if (!approval.approval_id) {
      setError("No approval ID -- cannot resolve. Try refreshing.");
      return;
    }
    setStatus(decision === "approved" ? "approving" : "rejecting");
    setError(null);
    try {
      const res = await fetch(`/api/ai/approvals/${approval.approval_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Failed (${res.status})`);
      }
      setStatus(decision === "approved" ? "approved" : "rejected");
      setTimeout(onResolved, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to resolve approval");
      setStatus("pending");
    }
  };

  const resolved = status === "approved" || status === "rejected";

  return (
    <div
      className={cn(
        "rounded-xl overflow-hidden my-3 transition-all duration-300 border",
        resolved
          ? "border-border bg-card opacity-70"
          : status === "pending"
            ? "border-warning bg-muted"
            : "border-border bg-muted"
      )}
    >
      <div className="px-4 py-3 flex items-start gap-3">
        {/* Icon */}
        <div
          className={cn(
            "mt-0.5 flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
            resolved
              ? status === "approved" ? "bg-success/15" : "bg-destructive/15"
              : "bg-warning/15"
          )}
        >
          {resolved ? (
            status === "approved" ? (
              <Check className="w-4 h-4 text-success" />
            ) : (
              <X className="w-4 h-4 text-destructive" />
            )
          ) : (
            <AlertCircle className="w-4 h-4 text-warning" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-warning">
              Approval Required
            </span>
            <span className="text-xs text-muted-foreground/70">
              {AGENT_LABELS[approval.agent] || approval.agent}
            </span>
          </div>
          <p className="text-sm font-medium mb-1 text-foreground">
            {approval.title}
          </p>
          {approval.content && (
            <p className="text-xs leading-relaxed line-clamp-3 text-muted-foreground">
              {approval.content.slice(0, 200)}{approval.content.length > 200 ? "..." : ""}
            </p>
          )}

          {error && (
            <p className="text-xs mt-2 text-destructive">{error}</p>
          )}
        </div>

        {/* Buttons */}
        {!resolved && (
          <div className="flex gap-2 flex-shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDecision("rejected")}
              disabled={status !== "pending"}
              className="text-xs text-destructive border-destructive/25 bg-destructive/10 hover:bg-destructive/20"
            >
              {status === "rejecting" ? "..." : "Reject"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDecision("approved")}
              disabled={status !== "pending"}
              className="text-xs text-success border-success/30 bg-success/15 hover:bg-success/25"
            >
              {status === "approving" ? "..." : "Approve"}
            </Button>
          </div>
        )}

        {/* Resolved badge */}
        {resolved && (
          <Badge variant={status === "approved" ? "success" : "destructive"} className="flex-shrink-0">
            {status === "approved" ? "Approved" : "Rejected"}
          </Badge>
        )}
      </div>
    </div>
  );
}

/* -- Completed Agent Summary (collapsed on finished messages) -- */

function CompletedAgentSummary({
  agentEvents,
  toolEvents,
}: {
  agentEvents: NonNullable<ChatMessage["agentEvents"]>;
  toolEvents?: ChatMessage["toolEvents"];
}) {
  const [expanded, setExpanded] = useState(false);

  const agents = useMemo(() => {
    const seen = new Set<string>();
    return agentEvents.filter((e) => {
      if (seen.has(e.agent)) return false;
      seen.add(e.agent);
      return e.agent !== "coach" && e.agent !== "respond" && e.agent !== "merge" && e.agent !== "approval_gate";
    });
  }, [agentEvents]);

  if (agents.length === 0) return null;

  const toolCount = toolEvents?.filter((e) => e.type === "end").length || 0;

  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-[11px] py-1 px-0 bg-transparent border-none cursor-pointer text-muted-foreground"
      >
        <Check className="h-3 w-3 text-success" />
        <span>
          {agents.length} agent{agents.length > 1 ? "s" : ""}
          {toolCount > 0 ? ` \u00B7 ${toolCount} tool call${toolCount > 1 ? "s" : ""}` : ""}
        </span>
        <ChevronDown
          className={cn("h-3 w-3 transition-transform duration-200", expanded && "rotate-180")}
        />
      </button>
      {expanded && (
        <div className="mt-1 space-y-2">
          <div className="flex flex-wrap gap-2">
            {agents.map((evt) => {
              const ended = agentEvents.some((e) => e.agent === evt.agent && e.status === "end");
              return (
                <Badge key={evt.agent} variant="info" className="gap-1">
                  {ended ? (
                    <Check className="h-3 w-3 text-success" />
                  ) : (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  )}
                  {AGENT_LABELS[evt.agent] || evt.agent}
                </Badge>
              );
            })}
          </div>
          {toolEvents && toolEvents.length > 0 && (
            <div className="space-y-1.5">
              {dedupToolEvents(toolEvents).map((evt, idx) => (
                <ToolCallBlock key={`completed-${evt.tool}-${idx}`} evt={evt} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Deduplicate tool events: keep end events over start, merge input from start into end */
function dedupToolEvents(events: ToolEvent[]): ToolEvent[] {
  const toolMap = new Map<string, ToolEvent>();
  for (const evt of events) {
    const existing = toolMap.get(evt.tool);
    if (evt.type === "end") {
      toolMap.set(evt.tool, { ...evt, input: existing?.input || evt.input });
    } else if (!existing) {
      toolMap.set(evt.tool, evt);
    }
  }
  return Array.from(toolMap.values());
}

/* -- Agent Stream Preview (live specialist output) -- */

function AgentStreamPreview({
  agentStreams,
  agentEvents,
  isLoading = false,
}: {
  agentStreams: Record<string, string>;
  agentEvents: NonNullable<ChatMessage["agentEvents"]>;
  isLoading?: boolean;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const scrollRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const agents = useMemo(() => Object.entries(agentStreams).filter(([, text]) => text.length > 0), [agentStreams]);
  if (agents.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {agents.map(([agent, text]) => {
        const ended = agentEvents.some((e) => e.agent === agent && e.status === "end");
        // While loading: expanded by default (user can collapse).
        // After loading: collapsed by default (user can expand). Avoids duplicating section cards.
        const userToggled = collapsed.has(agent);
        const showContent = isLoading ? !userToggled : userToggled;

        return (
          <div
            key={agent}
            className="rounded-lg overflow-hidden transition-all duration-200 border bg-card"
          >
            <button
              onClick={() => setCollapsed((prev) => {
                const next = new Set(prev);
                if (next.has(agent)) next.delete(agent);
                else next.add(agent);
                return next;
              })}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-left"
            >
              {!ended ? (
                <span className="h-2 w-2 flex-shrink-0 rounded-full bg-primary animate-pulse" />
              ) : (
                <Check className="h-3 w-3 flex-shrink-0 text-success" />
              )}
              <span className="text-[11px] font-medium text-muted-foreground">
                {AGENT_LABELS[agent] || agent}
              </span>
              <span className="flex-1" />
              <ChevronDown
                className={cn(
                  "h-3 w-3 flex-shrink-0 text-muted-foreground/70 transition-transform duration-200",
                  showContent && "rotate-180"
                )}
              />
            </button>
            {showContent && (
              <div
                ref={(el) => {
                  scrollRefs.current[agent] = el;
                  if (el) el.scrollTop = el.scrollHeight;
                }}
                className="px-3 py-2 max-h-60 overflow-auto text-xs leading-relaxed border-t text-muted-foreground"
              >
                <Markdown>{text}</Markdown>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
