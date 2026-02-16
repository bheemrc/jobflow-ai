"use client";

import { useRef, useEffect, useCallback, useState, useMemo } from "react";
import { MessageBubble } from "./message-bubble";
import { TypingIndicator } from "./typing-indicator";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import Markdown from "@/components/markdown";
import { cn } from "@/lib/utils";
import type { GroupChatMessage } from "@/lib/types";

// Debounce helper for scroll handler
function useDebounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  return useCallback((...args: Parameters<T>) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]) as T;
}

interface MessageListProps {
  messages: GroupChatMessage[];
  currentSpeaker: string | null;
  currentTurn: number;
  isActive: boolean;
  summary?: string | null;
}

// Track which messages have been rendered for animation
const renderedMessages = new Set<number>();

export function MessageList({
  messages,
  currentSpeaker,
  currentTurn,
  isActive,
  summary,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Track if user is near bottom (debounced to prevent jank)
  const updateScrollState = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 150;
    setShowScrollButton(distanceFromBottom > 300);
  }, []);

  const handleScroll = useDebounce(updateScrollState, 50);

  // Scroll to bottom when new messages arrive (if user is near bottom)
  useEffect(() => {
    if (shouldAutoScrollRef.current && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length]);

  // Initial scroll to bottom
  useEffect(() => {
    if (messages.length > 0 && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "instant" });
    }
  }, []);

  // Mark messages as rendered after animation
  useEffect(() => {
    messages.forEach((m) => {
      setTimeout(() => {
        renderedMessages.add(m.id);
      }, 500);
    });
  }, [messages]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  if (messages.length === 0 && !currentSpeaker) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
        <div className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4 animate-float bg-primary/10">
          <svg
            className="h-8 w-8 text-primary"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
            />
          </svg>
        </div>
        <p className="text-[15px] font-semibold mb-1 text-foreground">
          Discussion Starting
        </p>
        <p className="text-[13px] text-muted-foreground">
          Agents are preparing to contribute their perspectives
        </p>

        {/* Animated dots */}
        <div className="flex items-center gap-1.5 mt-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-2 w-2 rounded-full bg-primary animate-typing-dot"
              style={{
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 relative">
      <div
        ref={containerRef}
        className="absolute inset-0 overflow-y-auto p-5 scroll-smooth"
        onScroll={handleScroll}
      >
        <div className="space-y-4 max-w-4xl mx-auto">
          {messages.map((message, i) => {
            const isNew = !renderedMessages.has(message.id);
            return (
              <div
                key={message.id}
                className={isNew ? "animate-slide-in-message" : ""}
                style={isNew ? { animationDelay: `${Math.min(i * 50, 200)}ms` } : undefined}
              >
                <MessageBubble
                  message={message}
                  isLatest={i === messages.length - 1 && !currentSpeaker}
                />
              </div>
            );
          })}

          {/* Typing indicator */}
          {currentSpeaker && isActive && (
            <TypingIndicator agent={currentSpeaker} turn={currentTurn} />
          )}

          {/* Summary card for concluded chats */}
          {summary && (
            <div className="animate-slide-in-message">
              <Card className="p-6 bg-gradient-to-br from-purple-500/10 to-blue-500/5 border-purple-500/25">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-xl flex items-center justify-center bg-purple-500/15">
                    <span className="text-xl">{"\uD83E\uDDEC"}</span>
                  </div>
                  <div>
                    <h3 className="text-[15px] font-bold text-purple-400">
                      Synthesis
                    </h3>
                    <p className="text-[11px] text-muted-foreground">
                      Key findings from this discussion
                    </p>
                  </div>
                </div>
                <div className="text-[14px] leading-[1.7] text-foreground synthesis-content">
                  <Markdown>{summary}</Markdown>
                </div>
              </Card>
            </div>
          )}

          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <Button
          onClick={scrollToBottom}
          variant="outline"
          size="icon"
          className="absolute bottom-6 right-6 rounded-full shadow-lg hover:scale-110 animate-fade-in"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </Button>
      )}
    </div>
  );
}
