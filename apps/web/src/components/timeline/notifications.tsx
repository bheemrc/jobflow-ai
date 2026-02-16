"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { AgentPersonality } from "@/lib/use-timeline-events";
import { resolveAgent } from "@/lib/use-timeline-events";

export interface Notification {
  id: string;
  agent: string;
  message: string;
  type: "post" | "reply" | "mention" | "swarm" | "phase" | "error";
  timestamp: number;
}

interface NotificationToastProps {
  notifications: Notification[];
  agents: Record<string, AgentPersonality>;
  onDismiss: (id: string) => void;
}

export function NotificationToast({ notifications, agents, onDismiss }: NotificationToastProps) {
  if (notifications.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {notifications.slice(0, 3).map((notif) => {
        const agent = resolveAgent(notif.agent, agents);
        const typeColors: Record<string, string> = {
          post: "#58A6FF",
          reply: "#A78BFA",
          mention: "#F97316",
          swarm: "#818CF8",
          phase: "#22D3EE",
          error: "#EF4444",
        };
        const color = typeColors[notif.type] || "#58A6FF";

        return (
          <Card
            key={notif.id}
            className="animate-slide-in-right px-4 py-3 backdrop-blur-xl bg-card/95 shadow-lg"
            style={{
              borderColor: `${color}25`,
            }}
          >
            <div className="flex items-start gap-3">
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm"
                style={{ background: `${color}15`, border: `1px solid ${color}25` }}
              >
                {agent.avatar}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] font-bold" style={{ color }}>
                    {agent.displayName}
                  </span>
                  <span
                    className="text-[8px] font-bold uppercase tracking-wider px-1 py-0.5 rounded"
                    style={{ background: `${color}12`, color }}
                  >
                    {notif.type}
                  </span>
                </div>
                <p className="text-[11px] mt-0.5 line-clamp-2 text-muted-foreground">
                  {notif.message}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={() => onDismiss(notif.id)}
              >
                <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </Button>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [history, setHistory] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const counterRef = useRef(0);

  const addNotification = useCallback((agent: string, message: string, type: Notification["type"]) => {
    counterRef.current++;
    const notif: Notification = {
      id: `notif-${counterRef.current}`,
      agent,
      message,
      type,
      timestamp: Date.now(),
    };
    setNotifications((prev) => [notif, ...prev].slice(0, 10));
    setHistory((prev) => [notif, ...prev].slice(0, 50));
    setUnreadCount((prev) => prev + 1);

    // Auto-dismiss toast after 5 seconds
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== notif.id));
    }, 5000);
  }, []);

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const markAllRead = useCallback(() => {
    setUnreadCount(0);
  }, []);

  return { notifications, history, unreadCount, addNotification, dismissNotification, markAllRead };
}

// ===============================================================
// NOTIFICATION BELL -- dropdown with recent notifications
// ===============================================================

interface NotificationBellProps {
  history: Notification[];
  unreadCount: number;
  agents: Record<string, AgentPersonality>;
  onMarkRead: () => void;
}

function timeAgo(ts: number): string {
  const diffSec = Math.floor((Date.now() - ts) / 1000);
  if (diffSec < 60) return "now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  return `${Math.floor(diffHr / 24)}d`;
}

export function NotificationBell({ history, unreadCount, agents, onMarkRead }: NotificationBellProps) {
  const [open, setOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleToggle = () => {
    setOpen((prev) => !prev);
    if (!open && unreadCount > 0) onMarkRead();
  };

  const typeColors: Record<string, string> = {
    post: "#58A6FF",
    reply: "#A78BFA",
    mention: "#F97316",
    swarm: "#818CF8",
    phase: "#22D3EE",
    error: "#EF4444",
  };

  return (
    <div ref={bellRef} className="relative">
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          "relative h-9 w-9 rounded-xl",
          open && "bg-accent",
          unreadCount > 0 ? "text-foreground" : "text-muted-foreground"
        )}
        onClick={handleToggle}
        title="Notifications"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 h-4 min-w-[16px] px-1 rounded-full flex items-center justify-center text-[8px] font-bold animate-scale-in bg-destructive text-white shadow-[0_0_8px_rgba(239,68,68,0.4)]">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <Card className="absolute right-0 top-full mt-2 w-[300px] rounded-xl overflow-hidden animate-scale-in z-50 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <span className="text-[12px] font-bold text-foreground">
              Notifications
            </span>
            {history.length > 0 && (
              <span className="text-[9px] data-mono text-muted-foreground">
                {history.length} total
              </span>
            )}
          </div>

          <div className="max-h-[320px] overflow-y-auto">
            {history.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <div className="text-[20px] mb-2">&#x1F514;</div>
                <p className="text-[11px] text-muted-foreground">
                  No notifications yet
                </p>
                <p className="text-[9px] mt-1 text-muted-foreground">
                  Agent signals will appear here
                </p>
              </div>
            ) : (
              history.slice(0, 15).map((notif) => {
                const agent = resolveAgent(notif.agent, agents);
                const color = typeColors[notif.type] || "#58A6FF";
                return (
                  <div
                    key={notif.id}
                    className="flex items-start gap-2.5 px-4 py-2.5 transition-colors border-b hover:bg-accent"
                  >
                    <div
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs mt-0.5"
                      style={{ background: `${color}12`, border: `1px solid ${color}20` }}
                    >
                      {agent.avatar}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-semibold" style={{ color }}>
                          {agent.displayName}
                        </span>
                        <span className="text-[8px] data-mono text-muted-foreground">
                          {timeAgo(notif.timestamp)}
                        </span>
                      </div>
                      <p className="text-[10px] mt-0.5 line-clamp-2 text-muted-foreground">
                        {notif.message}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
