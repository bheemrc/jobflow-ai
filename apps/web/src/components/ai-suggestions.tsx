"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface AISuggestionsProps {
  resumeId: string | null;
}

export default function AISuggestions({ resumeId }: AISuggestionsProps) {
  const [roleInput, setRoleInput] = useState("");
  const [roleSuggestions, setRoleSuggestions] = useState<string | null>(null);
  const [locationSuggestions, setLocationSuggestions] = useState<string | null>(null);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [loadingLocations, setLoadingLocations] = useState(false);

  async function handleSuggestRoles() {
    if (!roleInput.trim()) return;
    setLoadingRoles(true);
    try {
      const res = await fetch("/api/ai/suggest-roles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_role: roleInput }),
      });
      if (res.ok) {
        const data = await res.json();
        setRoleSuggestions(data.suggestions);
      }
    } catch {
      setRoleSuggestions("Failed to get suggestions. Is the AI service running?");
    } finally {
      setLoadingRoles(false);
    }
  }

  async function handleSuggestLocations() {
    if (!roleInput.trim()) return;
    setLoadingLocations(true);
    try {
      const res = await fetch("/api/ai/suggest-locations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: roleInput }),
      });
      if (res.ok) {
        const data = await res.json();
        setLocationSuggestions(data.suggestions);
      }
    } catch {
      setLocationSuggestions("Failed to get suggestions. Is the AI service running?");
    } finally {
      setLoadingLocations(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Role input */}
      <Card className="p-4">
        <h3 className="mb-2 text-sm font-semibold text-foreground">AI Suggestions</h3>
        <Input
          type="text"
          value={roleInput}
          onChange={(e) => setRoleInput(e.target.value)}
          placeholder="Enter your target role..."
          className="text-xs"
        />
        <div className="mt-2 flex gap-2">
          <Button
            onClick={handleSuggestRoles}
            disabled={loadingRoles || !roleInput.trim()}
            className="flex-1 text-xs"
            size="sm"
          >
            {loadingRoles ? "Loading..." : "Suggest Roles"}
          </Button>
          <Button
            onClick={handleSuggestLocations}
            disabled={loadingLocations || !roleInput.trim()}
            variant="secondary"
            className="flex-1 text-xs"
            size="sm"
          >
            {loadingLocations ? "Loading..." : "Suggest Locations"}
          </Button>
        </div>
      </Card>

      {/* Role suggestions */}
      {roleSuggestions && (
        <Card className="border-primary/20 bg-primary/5 p-4">
          <h4 className="mb-2 text-xs font-semibold text-foreground">Alternative Roles</h4>
          <div className="text-xs text-muted-foreground whitespace-pre-wrap">{roleSuggestions}</div>
          <button
            onClick={() => setRoleSuggestions(null)}
            className="mt-2 text-xs text-primary hover:underline"
          >
            Dismiss
          </button>
        </Card>
      )}

      {/* Location suggestions */}
      {locationSuggestions && (
        <Card className="border-primary/20 bg-primary/5 p-4">
          <h4 className="mb-2 text-xs font-semibold text-foreground">Recommended Locations</h4>
          <div className="text-xs text-muted-foreground whitespace-pre-wrap">{locationSuggestions}</div>
          <button
            onClick={() => setLocationSuggestions(null)}
            className="mt-2 text-xs text-primary hover:underline"
          >
            Dismiss
          </button>
        </Card>
      )}
    </div>
  );
}
