"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { MessageList, ChatSidebar, AgentAvatar, getAgentConfig } from "@/components/group-chat";
import { useGroupChatEvents } from "@/lib/use-group-chat-events";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { GroupChat, GroupChatMessage } from "@/lib/types";

export default function GroupChatPage({ params }: { params: { id: string } }) {
  const chatId = Number(params.id);

  const [chat, setChat] = useState<GroupChat | null>(null);
  const [messages, setMessages] = useState<GroupChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showWarning, setShowWarning] = useState(false);
  const [warningMessage, setWarningMessage] = useState("");
  const [activeToolCalls, setActiveToolCalls] = useState<{agent: string; tool: string; turn: number}[]>([]);

  // SSE event handlers - memoized to prevent hook re-renders
  const handleNewMessage = useCallback((message: GroupChatMessage) => {
    setMessages((prev) => {
      // Avoid duplicates by ID
      if (prev.some((m) => m.id === message.id)) {
        return prev;
      }
      return [...prev, message];
    });
    // Update chat stats
    setChat((prev) =>
      prev
        ? {
            ...prev,
            turns_used: message.turn_number,
            tokens_used: prev.tokens_used + (message.tokens_used || 0),
          }
        : null
    );
  }, []);

  const handleTurnStart = useCallback((agent: string, turn: number) => {
    // Could add sound or visual notification here
  }, []);

  const handleConcluded = useCallback((summary: string) => {
    setChat((prev) =>
      prev ? { ...prev, status: "concluded", summary } : null
    );
  }, []);

  const handleWarning = useCallback((message: string) => {
    setWarningMessage(message);
    setShowWarning(true);
    // Auto-hide after 5 seconds
    setTimeout(() => setShowWarning(false), 5000);
  }, []);

  const handleError = useCallback((err: string) => {
    console.error("SSE error:", err);
  }, []);

  const handleParticipantJoined = useCallback((agent: string, reason: string) => {
    // Add new participant to chat state
    setChat((prev) => {
      if (!prev) return null;
      if (prev.participants.includes(agent)) return prev;
      return {
        ...prev,
        participants: [...prev.participants, agent],
      };
    });
  }, []);

  const handleToolCall = useCallback((toolCall: {agent: string; turn: number; tool_name: string; status: string}) => {
    if (toolCall.status === "started") {
      setActiveToolCalls((prev) => [...prev, {agent: toolCall.agent, tool: toolCall.tool_name, turn: toolCall.turn}]);
    } else {
      // Remove completed tool call
      setActiveToolCalls((prev) => prev.filter(
        (tc) => !(tc.agent === toolCall.agent && tc.tool === toolCall.tool_name && tc.turn === toolCall.turn)
      ));
    }
  }, []);

  // Connect to SSE - only when chat is active
  const { connected, currentSpeaker, currentTurn, disconnect } = useGroupChatEvents({
    groupChatId: chatId,
    onMessage: handleNewMessage,
    onTurnStart: handleTurnStart,
    onConcluded: handleConcluded,
    onWarning: handleWarning,
    onError: handleError,
    onParticipantJoined: handleParticipantJoined,
    onToolCall: handleToolCall,
    enabled: !!chat && chat.status !== "concluded",
  });

  // Fetch initial data
  useEffect(() => {
    const fetchChat = async () => {
      try {
        const res = await fetch(`/api/ai/group-chats/${chatId}`);
        if (!res.ok) {
          setError("Chat not found");
          return;
        }
        const data = await res.json();
        setChat(data.group_chat);
        setMessages(data.messages || []);
      } catch (e) {
        console.error("Failed to fetch chat:", e);
        setError("Failed to load chat");
      } finally {
        setIsLoading(false);
      }
    };

    if (chatId) fetchChat();
  }, [chatId]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Actions
  const handlePause = async () => {
    await fetch(`/api/ai/group-chats/${chatId}/pause`, { method: "POST" });
    setChat((prev) => (prev ? { ...prev, status: "paused" } : null));
  };

  const handleResume = async () => {
    await fetch(`/api/ai/group-chats/${chatId}/resume`, { method: "POST" });
    setChat((prev) => (prev ? { ...prev, status: "active" } : null));
  };

  const handleConclude = async () => {
    await fetch(`/api/ai/group-chats/${chatId}/conclude`, { method: "POST" });
  };

  // Compute progress percentages
  const progressData = useMemo(() => {
    if (!chat) return { turns: 0, tokens: 0 };
    const maxTurns = chat.config?.max_turns || chat.max_turns || 20;
    const maxTokens = chat.config?.max_tokens || chat.max_tokens || 50000;
    return {
      turns: Math.min((chat.turns_used / maxTurns) * 100, 100),
      tokens: Math.min((chat.tokens_used / maxTokens) * 100, 100),
    };
  }, [chat]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="h-12 w-12 rounded-2xl flex items-center justify-center bg-primary/10">
              <svg
                className="h-6 w-6 animate-pulse text-primary"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
            </div>
            <div className="absolute inset-0 rounded-2xl animate-ping opacity-30 bg-primary" />
          </div>
          <p className="text-[14px] font-medium text-muted-foreground">
            Loading discussion...
          </p>
        </div>
      </div>
    );
  }

  if (error || !chat) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="h-16 w-16 mx-auto rounded-2xl flex items-center justify-center mb-4 bg-destructive/10">
            <svg
              className="h-8 w-8 text-destructive"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h2 className="text-[18px] font-bold mb-2 text-foreground">
            {error || "Chat not found"}
          </h2>
          <p className="text-[13px] mb-4 text-muted-foreground">
            This discussion may have been deleted or moved.
          </p>
          <Button asChild variant="outline">
            <Link href="/group-chats" className="inline-flex items-center gap-2">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back to discussions
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-screen overflow-hidden bg-background">
      {/* Warning toast */}
      {showWarning && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-xl flex items-center gap-3 animate-slide-in-message shadow-lg bg-warning/10 border border-warning">
          <svg
            className="h-5 w-5 shrink-0 text-warning"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <span className="text-[13px] font-medium text-warning">
            {warningMessage}
          </span>
          <Button
            onClick={() => setShowWarning(false)}
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-warning hover:bg-accent"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </Button>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="shrink-0 px-5 py-3 flex items-center gap-4 bg-card border-b">
          <Link
            href="/group-chats"
            className="p-2 rounded-xl transition-colors text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </Link>

          <div className="flex-1 min-w-0">
            <h1 className="text-[16px] font-bold truncate text-foreground">
              {chat.topic}
            </h1>
            <div className="flex items-center gap-3 mt-0.5">
              {/* Connection status */}
              <div className="flex items-center gap-1.5">
                <span
                  className={cn("h-2 w-2 rounded-full", connected && "animate-pulse")}
                  style={{
                    background: connected
                      ? "hsl(var(--success))"
                      : chat.status === "concluded"
                      ? "hsl(var(--muted-foreground))"
                      : "hsl(var(--destructive))",
                    boxShadow: connected ? "0 0 8px hsl(var(--success))" : "none",
                  }}
                />
                <span className="text-[11px] text-muted-foreground">
                  {chat.status === "concluded"
                    ? "Concluded"
                    : connected
                    ? "Live"
                    : "Reconnecting..."}
                </span>
              </div>

              {/* Progress indicator (compact) */}
              {chat.status === "active" && (
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1 rounded-full overflow-hidden bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-500",
                        progressData.turns > 80 ? "bg-warning" : "bg-primary"
                      )}
                      style={{ width: `${progressData.turns}%` }}
                    />
                  </div>
                  <span className="text-[10px] data-mono text-muted-foreground">
                    {chat.turns_used}/{chat.config?.max_turns || chat.max_turns || 20}
                  </span>
                </div>
              )}

              {/* Current speaker indicator */}
              {currentSpeaker && (
                <div className="flex items-center gap-1.5 animate-fade-in">
                  <AgentAvatar agent={currentSpeaker} size="xs" />
                  <span
                    className="text-[11px] font-medium"
                    style={{ color: getAgentConfig(currentSpeaker).color }}
                  >
                    {getAgentConfig(currentSpeaker).name} typing...
                  </span>
                </div>
              )}

              {/* Active tool calls indicator */}
              {activeToolCalls.length > 0 && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg animate-fade-in bg-primary/10">
                  <svg className="h-3 w-3 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="text-[10px] font-medium text-primary">
                    {activeToolCalls[0].tool.replace(/_/g, " ")}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {chat.status === "active" && (
              <>
                <Button
                  onClick={handlePause}
                  variant="ghost"
                  size="sm"
                  className="text-[12px] hover:scale-105 transition-all"
                >
                  <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                  </svg>
                  Pause
                </Button>
                <Button
                  onClick={handleConclude}
                  variant="outline"
                  size="sm"
                  className="text-[12px] text-warning border-warning hover:bg-warning/10 hover:scale-105 transition-all"
                >
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  Conclude
                </Button>
              </>
            )}
            {chat.status === "paused" && (
              <Button
                onClick={handleResume}
                size="sm"
                className="text-[12px] hover:scale-105 transition-all"
              >
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
                Resume
              </Button>
            )}
            <Button
              onClick={() => setShowSidebar(!showSidebar)}
              variant="ghost"
              size="icon"
              className={cn(!showSidebar && "opacity-50")}
              title={showSidebar ? "Hide sidebar" : "Show sidebar"}
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h7" />
              </svg>
            </Button>
          </div>
        </header>

        {/* Messages */}
        <MessageList
          messages={messages}
          currentSpeaker={currentSpeaker}
          currentTurn={currentTurn}
          isActive={chat.status === "active"}
          summary={chat.status === "concluded" ? chat.summary : null}
        />
      </div>

      {/* Sidebar */}
      {showSidebar && <ChatSidebar chat={chat} currentSpeaker={currentSpeaker} />}
    </div>
  );
}
