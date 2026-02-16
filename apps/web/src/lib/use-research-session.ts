"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface ResearchAgent {
  id: string;
  name: string;
  avatar: string;
  expertise: string;
  tone: string;
  status: "waiting" | "searching" | "found" | "debating" | "done";
  currentQuery?: string;
  findingPreview?: string;
  searchCount: number;
  resultCount: number;
}

export interface ResearchEvent {
  type: string;
  timestamp: string;
  agent_id?: string;
  agent_name?: string;
  avatar?: string;
  query?: string;
  result_count?: number;
  snippet?: string;
  content?: string;
  phase?: string;
  error?: string;
}

export interface ResearchSession {
  id: string;
  topic: string;
  status: "pending" | "spawning" | "researching" | "debating" | "synthesizing" | "building" | "complete" | "cancelled" | "error";
  startedAt: number;
  intent?: "build" | "analyze" | "troubleshoot" | "learn" | "compare";
  domain?: string;
}

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000];

export function useResearchSession() {
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [agents, setAgents] = useState<ResearchAgent[]>([]);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [synthesis, setSynthesis] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const sessionIdRef = useRef<string | null>(null);

  // Batch synthesis chunks: accumulate in ref, flush to state once per frame
  const synthChunkBuffer = useRef<string[]>([]);
  const synthRafRef = useRef<number>(0);

  const addEvent = useCallback((event: ResearchEvent) => {
    setEvents((prev) => [...prev.slice(-99), event]); // Keep last 100 events
  }, []);

  const handleEvent = useCallback((event: Record<string, unknown>) => {
    // Only process events for our session
    if (event.session_id && event.session_id !== sessionIdRef.current) {
      return;
    }

    const timestamp = (event.timestamp as string) || new Date().toISOString();

    switch (event.type) {
      case "research_phase": {
        const phase = event.phase as string;
        const intent = event.intent as ResearchSession["intent"] | undefined;
        const domain = event.domain as string | undefined;
        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            status: phase as ResearchSession["status"],
            ...(intent && { intent }),
            ...(domain && { domain }),
          };
        });
        addEvent({ type: "research_phase", timestamp, phase });
        break;
      }

      case "research_agents_spawned": {
        const agentsData = event.agents as Array<{
          id: string;
          name: string;
          avatar: string;
          expertise: string;
          tone: string;
        }>;
        const intent = event.intent as ResearchSession["intent"] | undefined;
        setAgents(
          agentsData.map((a) => ({
            ...a,
            status: "waiting" as const,
            searchCount: 0,
            resultCount: 0,
          }))
        );
        // Update session with intent if provided
        if (intent) {
          setSession((prev) => prev ? { ...prev, intent } : prev);
        }
        addEvent({
          type: "research_agents_spawned",
          timestamp,
          content: `Spawned ${agentsData.length} agents: ${agentsData.map((a) => a.name).join(", ")}`,
        });
        break;
      }

      case "agent_search_started": {
        const agentId = event.agent_id as string;
        const query = event.query as string;
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId
              ? { ...a, status: "searching" as const, currentQuery: query, searchCount: a.searchCount + 1 }
              : a
          )
        );
        addEvent({
          type: "agent_search_started",
          timestamp,
          agent_id: agentId,
          agent_name: event.agent_name as string,
          query,
        });
        break;
      }

      case "agent_search_result": {
        const agentId = event.agent_id as string;
        const resultCount = (event.result_count as number) || 0;
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId
              ? { ...a, resultCount: a.resultCount + resultCount }
              : a
          )
        );
        addEvent({
          type: "agent_search_result",
          timestamp,
          agent_id: agentId,
          agent_name: event.agent_name as string,
          query: event.query as string,
          result_count: resultCount,
          snippet: event.snippet as string,
        });
        break;
      }

      case "agent_finding": {
        const agentId = event.agent_id as string;
        const content = event.content as string;
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId
              ? { ...a, status: "found" as const, findingPreview: content, currentQuery: undefined }
              : a
          )
        );
        addEvent({
          type: "agent_finding",
          timestamp,
          agent_id: agentId,
          agent_name: event.agent_name as string,
          avatar: event.avatar as string,
          content,
        });
        break;
      }

      case "debate_started": {
        const agentId = event.agent_id as string;
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId ? { ...a, status: "debating" as const } : a
          )
        );
        break;
      }

      case "debate_turn": {
        const agentId = event.agent_id as string;
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId ? { ...a, status: "done" as const } : a
          )
        );
        addEvent({
          type: "debate_turn",
          timestamp,
          agent_id: agentId,
          agent_name: event.agent_name as string,
          avatar: event.avatar as string,
          content: event.content as string,
        });
        break;
      }

      case "research_synthesis_chunk": {
        const chunk = event.chunk as string;
        synthChunkBuffer.current.push(chunk);
        // Batch: flush accumulated chunks to React state once per animation frame
        if (!synthRafRef.current) {
          synthRafRef.current = requestAnimationFrame(() => {
            const pending = synthChunkBuffer.current.join("");
            synthChunkBuffer.current = [];
            synthRafRef.current = 0;
            setSynthesis((prev) => prev + pending);
          });
        }
        break;
      }

      case "research_synthesis": {
        // Final complete synthesis — replace accumulated chunks to ensure accuracy
        const content = event.content as string;
        setSynthesis(content);
        addEvent({
          type: "research_synthesis",
          timestamp,
          content,
        });
        break;
      }

      case "research_complete": {
        setSession((prev) => (prev ? { ...prev, status: "complete" } : prev));
        setAgents((prev) => prev.map((a) => ({ ...a, status: "done" as const })));
        addEvent({ type: "research_complete", timestamp });
        break;
      }

      case "research_error": {
        setSession((prev) => (prev ? { ...prev, status: "error" } : prev));
        setError(event.error as string);
        addEvent({
          type: "research_error",
          timestamp,
          error: event.error as string,
        });
        break;
      }

      case "heartbeat":
        reconnectAttemptRef.current = 0;
        break;
    }
  }, [addEvent]);

  // Connect to SSE stream immediately (before session starts)
  // This ensures we don't miss any events
  useEffect(() => {
    const connect = () => {
      eventSourceRef.current?.close();
      const es = new EventSource("/api/ai/timeline/stream");
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        reconnectAttemptRef.current = 0;
      };

      es.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          handleEvent(event);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
        setConnected(false);
        const attempt = Math.min(
          reconnectAttemptRef.current,
          RECONNECT_DELAYS.length - 1
        );
        const delay = RECONNECT_DELAYS[attempt];
        reconnectAttemptRef.current++;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [handleEvent]);

  const startSession = useCallback(async (topic: string): Promise<string | null> => {
    setError(null);
    setEvents([]);
    setAgents([]);
    setSynthesis("");

    try {
      const res = await fetch("/api/ai/research/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to start research session");
      }

      const { session_id } = await res.json();

      // Set sessionIdRef immediately so event handler can filter events
      sessionIdRef.current = session_id;

      setSession({
        id: session_id,
        topic,
        status: "pending",
        startedAt: Date.now(),
      });

      return session_id;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start session");
      return null;
    }
  }, []);

  const stopSession = useCallback(async () => {
    if (!session) return;

    try {
      await fetch(`/api/ai/research/sessions/${session.id}`, {
        method: "DELETE",
      });
      setSession((prev) => (prev ? { ...prev, status: "cancelled" } : prev));
    } catch {
      // ignore errors
    }
  }, [session]);

  const reset = useCallback(() => {
    // Don't close the SSE connection - just reset the session state
    sessionIdRef.current = null;
    synthChunkBuffer.current = [];
    if (synthRafRef.current) cancelAnimationFrame(synthRafRef.current);
    synthRafRef.current = 0;
    setSession(null);
    setAgents([]);
    setEvents([]);
    setSynthesis("");
    setError(null);
  }, []);

  return {
    session,
    agents,
    events,
    synthesis,
    error,
    connected,
    startSession,
    stopSession,
    reset,
  };
}
