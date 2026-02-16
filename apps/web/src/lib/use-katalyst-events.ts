"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface Reaction {
  id: number;
  goal: string;
  status: string;
  lead_agent: string;
  phases: { name: string; status: string; order: number }[];
  context: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  workstreams?: Workstream[];
  artifacts?: Artifact[];
  blockers?: Blocker[];
}

export interface Workstream {
  id: number;
  reaction_id: number;
  title: string;
  description: string;
  agent: string;
  status: string;
  phase: string;
  progress: number;
  output: string;
  created_at: string;
}

export interface Artifact {
  id: number;
  reaction_id: number;
  workstream_id: number | null;
  title: string;
  artifact_type: string;
  content: string;
  version: number;
  status: string;
  agent: string;
  metadata: Record<string, unknown>;
  created_at: string;
  versions?: Artifact[];
}

export interface Blocker {
  id: number;
  reaction_id: number;
  workstream_id: number | null;
  title: string;
  description: string;
  severity: string;
  agent: string;
  options: { label: string; description: string }[];
  auto_resolve_confidence: number;
  resolution: string;
  resolved_by: string;
  created_at: string;
  resolved_at: string | null;
}

export interface KatalystEvent {
  id: number;
  reaction_id: number;
  event_type: string;
  agent: string;
  message: string;
  data: Record<string, unknown>;
  created_at: string;
}

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000];

export function useKatalystStream(reactionId: number) {
  const [reaction, setReaction] = useState<Reaction | null>(null);
  const [workstreams, setWorkstreams] = useState<Workstream[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [blockers, setBlockers] = useState<Blocker[]>([]);
  const [events, setEvents] = useState<KatalystEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleEvent = useCallback((event: Record<string, unknown>) => {
    switch (event.type) {
      case "katalyst_state":
        if (event.reaction) setReaction(event.reaction as Reaction);
        if (Array.isArray(event.workstreams)) setWorkstreams(event.workstreams as Workstream[]);
        if (Array.isArray(event.artifacts)) setArtifacts(event.artifacts as Artifact[]);
        if (Array.isArray(event.blockers)) setBlockers(event.blockers as Blocker[]);
        if (Array.isArray(event.events)) setEvents(event.events as KatalystEvent[]);
        break;

      case "katalyst_workstream_advanced":
        // Refresh workstreams
        fetch(`/api/ai/katalyst/reactions/${reactionId}/workstreams`)
          .then((r) => r.json())
          .then((d) => { if (d?.workstreams) setWorkstreams(d.workstreams); })
          .catch(() => {});
        break;

      case "katalyst_artifact_created":
      case "katalyst_artifact_updated":
        fetch(`/api/ai/katalyst/reactions/${reactionId}/artifacts`)
          .then((r) => r.json())
          .then((d) => { if (d?.artifacts) setArtifacts(d.artifacts); })
          .catch(() => {});
        break;

      case "katalyst_blocker_resolved":
      case "katalyst_blocker_created":
        fetch(`/api/ai/katalyst/reactions/${reactionId}/blockers`)
          .then((r) => r.json())
          .then((d) => { if (d?.blockers) setBlockers(d.blockers); })
          .catch(() => {});
        break;

      case "katalyst_reaction_completed":
        fetch(`/api/ai/katalyst/reactions/${reactionId}`)
          .then((r) => r.json())
          .then((d) => { if (d?.id) setReaction(d); })
          .catch(() => {});
        break;
    }
  }, [reactionId]);

  useEffect(() => {
    const connect = () => {
      eventSourceRef.current?.close();
      const es = new EventSource(`/api/ai/katalyst/reactions/${reactionId}/stream`);
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
  }, [handleEvent, reactionId]);

  return {
    reaction,
    workstreams,
    artifacts,
    blockers,
    events,
    connected,
    setReaction,
    setWorkstreams,
    setArtifacts,
    setBlockers,
  };
}
