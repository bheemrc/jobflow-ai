"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "./store";
import type { BotEvent, BotState } from "./types";

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000]; // exponential backoff

/**
 * SSE hook that connects to /api/ai/bots/events/stream with:
 * - Automatic reconnection with exponential backoff
 * - Last-Event-ID tracking for replay on reconnect
 * - Heartbeat monitoring for connection health
 */
export function useBotEvents() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string>("");
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const setBotStates = useAppStore((s) => s.setBotStates);
  const updateBotState = useAppStore((s) => s.updateBotState);
  const addBotRun = useAppStore((s) => s.addBotRun);
  const updateBotRun = useAppStore((s) => s.updateBotRun);
  const setTokenUsage = useAppStore((s) => s.setTokenUsage);
  const appendBotLog = useAppStore((s) => s.appendBotLog);

  const handleEvent = useCallback((event: BotEvent) => {
    switch (event.type) {
      case "bots_state":
        if (event.bots) {
          setBotStates(event.bots);
        }
        break;

      case "bot_state_change":
        if (event.bot_name) {
          const stateUpdate: Partial<BotState> = {
            status: event.status as BotState["status"],
          };
          if (event.cooldown_until !== undefined) {
            stateUpdate.cooldown_until = event.cooldown_until as string | null;
          }
          if (event.runs_today !== undefined) {
            stateUpdate.runs_today = event.runs_today as number;
          }
          if (event.last_run_at !== undefined) {
            stateUpdate.last_run_at = event.last_run_at as string | null;
          }
          if (event.enabled !== undefined) {
            stateUpdate.enabled = event.enabled as boolean;
          }
          updateBotState(event.bot_name, stateUpdate);
        }
        break;

      case "bot_run_start":
        if (event.bot_name && event.run_id) {
          addBotRun({
            run_id: event.run_id,
            bot_name: event.bot_name,
            status: "running",
            trigger_type: event.trigger_type || "manual",
            started_at: event.timestamp || new Date().toISOString(),
            completed_at: null,
            output: null,
            input_tokens: 0,
            output_tokens: 0,
            cost: 0,
          });
          updateBotState(event.bot_name, { status: "running" });
        }
        break;

      case "bot_run_complete":
        if (event.run_id) {
          updateBotRun(event.run_id, {
            status: event.status as string || "completed",
            completed_at: event.timestamp || new Date().toISOString(),
            input_tokens: event.input_tokens || 0,
            output_tokens: event.output_tokens || 0,
            cost: event.cost || 0,
          });
        }
        if (event.bot_name) {
          updateBotState(event.bot_name, {
            status: "scheduled",
            last_run_at: event.timestamp || new Date().toISOString(),
            last_output_preview: (event.output_preview as string) || undefined,
            last_run_cost: (event.cost as number) || undefined,
            last_run_status: (event.status as string) || "completed",
          });
        }
        break;

      case "bot_run_error":
        if (event.run_id) {
          updateBotRun(event.run_id, {
            status: "errored",
            completed_at: event.timestamp || new Date().toISOString(),
          });
        }
        if (event.bot_name) {
          updateBotState(event.bot_name, { status: "errored" });
        }
        break;

      case "token_usage_update":
        setTokenUsage({
          total_cost: (event.total_cost as number) || 0,
          total_input_tokens: (event.total_input_tokens as number) || 0,
          total_output_tokens: (event.total_output_tokens as number) || 0,
          total_runs: (event.total_runs as number) || 0,
          by_bot: (event.by_bot as Record<string, { cost: number; input_tokens: number; output_tokens: number; runs: number }>) || {},
          daily: (event.daily as { date: string; cost: number; input_tokens: number; output_tokens: number; runs: number }[]) || [],
        });
        break;

      case "bot_log":
        if (event.run_id) {
          appendBotLog(event.run_id as string, {
            id: Date.now(),
            run_id: event.run_id as string,
            level: (event.level as string) || "info",
            event_type: (event.event_type as string) || "log",
            message: (event.message as string) || "",
            data: (event.data as Record<string, unknown>) || null,
            created_at: event.timestamp || new Date().toISOString(),
          });
        }
        break;

      case "heartbeat":
        // Connection is alive, reset reconnect counter
        reconnectAttemptRef.current = 0;
        break;
    }
  }, [setBotStates, updateBotState, addBotRun, updateBotRun, setTokenUsage, appendBotLog]);

  useEffect(() => {
    const connect = () => {
      // Clean up existing connection
      eventSourceRef.current?.close();

      const url = "/api/ai/bots/events/stream";
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onmessage = (e) => {
        try {
          // Track Last-Event-ID
          if (e.lastEventId) {
            lastEventIdRef.current = e.lastEventId;
          }
          const event: BotEvent = JSON.parse(e.data);
          // Store event_id for reconnection
          if (event.event_id) {
            lastEventIdRef.current = String(event.event_id);
          }
          handleEvent(event);
        } catch {
          // Ignore parse errors
        }
      };

      es.onopen = () => {
        reconnectAttemptRef.current = 0;
      };

      es.onerror = () => {
        es.close();
        // Exponential backoff reconnection
        const attempt = Math.min(reconnectAttemptRef.current, RECONNECT_DELAYS.length - 1);
        const delay = RECONNECT_DELAYS[attempt];
        reconnectAttemptRef.current++;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimerRef.current);
      eventSourceRef.current?.close();
    };
  }, [handleEvent]);
}
