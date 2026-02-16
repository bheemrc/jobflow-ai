"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import type { GroupChatEvent, GroupChatMessage } from "./types";

// Reconnection delays with exponential backoff (capped at 30s)
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000, 30000];
// Heartbeat timeout (if no heartbeat in this time, reconnect)
const HEARTBEAT_TIMEOUT = 45000;

interface ToolCallEvent {
  agent: string;
  turn: number;
  tool_name: string;
  tool_args?: Record<string, unknown>;
  result_preview?: string;
  status: "started" | "completed";
}

interface UseGroupChatEventsOptions {
  groupChatId: number;
  onMessage?: (message: GroupChatMessage) => void;
  onTurnStart?: (agent: string, turn: number) => void;
  onConcluded?: (summary: string) => void;
  onWarning?: (message: string) => void;
  onError?: (error: string) => void;
  onParticipantJoined?: (agent: string, reason: string) => void;
  onToolCall?: (toolCall: ToolCallEvent) => void;
  enabled?: boolean; // Allow disabling the connection
}

interface ConnectionState {
  connected: boolean;
  currentSpeaker: string | null;
  currentTurn: number;
  lastEventTime: number;
}

export function useGroupChatEvents({
  groupChatId,
  onMessage,
  onTurnStart,
  onConcluded,
  onWarning,
  onError,
  onParticipantJoined,
  onToolCall,
  enabled = true,
}: UseGroupChatEventsOptions) {
  // Use refs to avoid re-creating callbacks on every render
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // Store callbacks in refs to avoid dependency issues
  const callbacksRef = useRef({ onMessage, onTurnStart, onConcluded, onWarning, onError, onParticipantJoined, onToolCall });
  callbacksRef.current = { onMessage, onTurnStart, onConcluded, onWarning, onError, onParticipantJoined, onToolCall };

  const [state, setState] = useState<ConnectionState>({
    connected: false,
    currentSpeaker: null,
    currentTurn: 0,
    lastEventTime: Date.now(),
  });

  // Cleanup function
  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Reset heartbeat timer
  const resetHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = setTimeout(() => {
      // No heartbeat received, reconnect
      if (mountedRef.current && eventSourceRef.current) {
        console.warn("[SSE] Heartbeat timeout, reconnecting...");
        eventSourceRef.current.close();
      }
    }, HEARTBEAT_TIMEOUT);
  }, []);

  // Handle incoming events with proper error boundaries
  const handleEvent = useCallback(
    (event: GroupChatEvent) => {
      if (!mountedRef.current) return;

      const cbs = callbacksRef.current;

      try {
        switch (event.type) {
          case "group_chat_turn_start":
            if (event.agent) {
              setState((s) => ({
                ...s,
                currentSpeaker: event.agent!,
                currentTurn: event.turn || 0,
                lastEventTime: Date.now(),
              }));
              cbs.onTurnStart?.(event.agent, event.turn || 0);
            }
            break;

          case "group_chat_message":
            setState((s) => ({
              ...s,
              currentSpeaker: null,
              lastEventTime: Date.now(),
            }));
            if (event.agent && event.content) {
              const message = {
                id: event.post_id || Date.now(),
                group_chat_id: event.group_chat_id || 0,
                agent: event.agent,
                turn_number: event.turn || 0,
                mentions: event.mentions || [],
                tokens_used: event.tokens_used || 0,
                user_id: "",
                created_at: event.timestamp || new Date().toISOString(),
                content: event.content,
              };
              cbs.onMessage?.(message);
            } else {
              console.warn("[SSE] Message missing agent or content:", event);
            }
            break;

          case "group_chat_concluded":
            setState((s) => ({ ...s, currentSpeaker: null, lastEventTime: Date.now() }));
            cbs.onConcluded?.(event.summary || "Discussion concluded.");
            break;

          case "group_chat_warning":
            cbs.onWarning?.(event.message || "Approaching budget limit.");
            break;

          case "group_chat_turn_error":
            cbs.onError?.(event.error || "Error during turn execution.");
            break;

          case "group_chat_paused":
            setState((s) => ({ ...s, currentSpeaker: null, lastEventTime: Date.now() }));
            break;

          case "group_chat_participant_joined":
            if (event.agent) {
              cbs.onParticipantJoined?.(event.agent, event.reason || "Joined dynamically");
            }
            break;

          case "group_chat_tool_call":
          case "group_chat_tool_result":
            if (event.agent && event.tool_name) {
              cbs.onToolCall?.({
                agent: event.agent,
                turn: event.turn || 0,
                tool_name: event.tool_name as string,
                tool_args: event.tool_args as Record<string, unknown> | undefined,
                result_preview: event.result_preview as string | undefined,
                status: event.type === "group_chat_tool_call" ? "started" : "completed",
              });
            }
            break;

          case "heartbeat":
          case "connected":
            // Reset heartbeat timer and reconnect counter
            reconnectAttemptRef.current = 0;
            resetHeartbeat();
            setState((s) => ({ ...s, lastEventTime: Date.now() }));
            break;
        }
      } catch (err) {
        console.error("[SSE] Error handling event:", err);
      }
    },
    [resetHeartbeat]
  );

  // Main connection effect
  useEffect(() => {
    if (!groupChatId || !enabled) {
      cleanup();
      return;
    }

    mountedRef.current = true;

    const connect = () => {
      if (!mountedRef.current) return;

      cleanup();

      const url = `/api/ai/group-chats/${groupChatId}/stream`;

      try {
        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.onmessage = (e) => {
          try {
            const event: GroupChatEvent = JSON.parse(e.data);
            handleEvent(event);
          } catch (parseErr) {
            // Silently ignore parse errors (might be comments or empty lines)
            console.debug("[SSE] Parse error or empty line:", e.data);
          }
        };

        es.onopen = () => {
          if (!mountedRef.current) {
            es.close();
            return;
          }
          setState((s) => ({ ...s, connected: true }));
          reconnectAttemptRef.current = 0;
          resetHeartbeat();
        };

        es.onerror = () => {
          if (!mountedRef.current) return;

          setState((s) => ({ ...s, connected: false }));
          es.close();
          eventSourceRef.current = null;

          // Exponential backoff for reconnection
          const attempt = Math.min(
            reconnectAttemptRef.current,
            RECONNECT_DELAYS.length - 1
          );
          const delay = RECONNECT_DELAYS[attempt];
          reconnectAttemptRef.current++;


          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current) {
              connect();
            }
          }, delay);
        };
      } catch (err) {
        console.error("[SSE] Failed to create EventSource:", err);
      }
    };

    // Small delay before connecting to avoid rapid connections during React strict mode
    const initialTimer = setTimeout(connect, 100);

    return () => {
      mountedRef.current = false;
      clearTimeout(initialTimer);
      cleanup();
    };
  }, [groupChatId, enabled, cleanup, handleEvent, resetHeartbeat]);

  // Memoize return value
  return useMemo(
    () => ({
      connected: state.connected,
      currentSpeaker: state.currentSpeaker,
      currentTurn: state.currentTurn,
      disconnect: cleanup,
    }),
    [state.connected, state.currentSpeaker, state.currentTurn, cleanup]
  );
}
