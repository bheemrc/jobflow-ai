import { useState, useCallback, useRef, useEffect } from "react";

// Use the Next.js API proxy to reach the AI service
const CONFIG_API_BASE = "/api/ai";

interface UseFlowConfigReturn {
  yaml: string;
  setYaml: (yaml: string) => void;
  save: () => Promise<{ ok: boolean; error?: string; agents?: string[] }>;
  reset: () => Promise<void>;
  isSaving: boolean;
  isLoading: boolean;
  error: string | null;
  isDirty: boolean;
  lastSavedYaml: string;
}

export function useFlowConfig(): UseFlowConfigReturn {
  const [yaml, setYaml] = useState("");
  const [lastSavedYaml, setLastSavedYaml] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loaded = useRef(false);

  const isDirty = yaml !== lastSavedYaml && lastSavedYaml !== "";

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CONFIG_API_BASE}/config/flows`);
      if (!res.ok) throw new Error(`Failed to load config (${res.status})`);
      const data = await res.json();
      const text = data.yaml || "";
      setYaml(text);
      setLastSavedYaml(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load config");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!loaded.current) {
      loaded.current = true;
      load();
    }
  }, [load]);

  const save = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    try {
      const res = await fetch(`${CONFIG_API_BASE}/config/flows`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml_text: yaml }),
      });
      const data = await res.json();
      if (data.ok) {
        setLastSavedYaml(yaml);
        return { ok: true, agents: data.agents };
      } else {
        const errMsg = data.error || "Unknown error";
        setError(errMsg);
        return { ok: false, error: errMsg };
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "Failed to save config";
      setError(errMsg);
      return { ok: false, error: errMsg };
    } finally {
      setIsSaving(false);
    }
  }, [yaml]);

  const reset = useCallback(async () => {
    await load();
  }, [load]);

  return {
    yaml,
    setYaml,
    save,
    reset,
    isSaving,
    isLoading,
    error,
    isDirty,
    lastSavedYaml,
  };
}
