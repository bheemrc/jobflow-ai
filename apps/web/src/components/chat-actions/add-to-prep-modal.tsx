"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";

interface AddToPrepModalProps {
  content: string;
  company?: string;
  role?: string;
  onClose: () => void;
}

const MATERIAL_TYPES = [
  { value: "interview", label: "Interview" },
  { value: "system_design", label: "System Design" },
  { value: "leetcode", label: "LeetCode" },
  { value: "company_research", label: "Company Research" },
  { value: "general", label: "General" },
];

export default function AddToPrepModal({ content, company, role, onClose }: AddToPrepModalProps) {
  const [title, setTitle] = useState(
    content.replace(/[#*_\n]/g, " ").trim().slice(0, 60) || "Chat excerpt"
  );
  const [materialType, setMaterialType] = useState("general");
  const [companyVal, setCompanyVal] = useState(company || "");
  const [roleVal, setRoleVal] = useState(role || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/ai/prep/materials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material_type: materialType,
          title,
          content,
          company: companyVal || null,
          role: roleVal || null,
          agent_source: "chat",
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Failed (${res.status})`);
      }
      setSaved(true);
      setTimeout(onClose, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">Add to Prep</DialogTitle>
          <DialogDescription className="sr-only">Save content as prep material</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label className="text-[11px] mb-1 block">Title</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded-lg text-sm"
              maxLength={120}
            />
          </div>

          <div>
            <Label className="text-[11px] mb-1.5 block">Type</Label>
            <div className="flex flex-wrap gap-1.5">
              {MATERIAL_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setMaterialType(t.value)}
                  className={cn(
                    "rounded-full px-3 py-1 text-[11px] font-medium transition-colors border",
                    materialType === t.value
                      ? "bg-primary/10 text-primary border-primary/30"
                      : "bg-card text-muted-foreground border-border"
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[11px] mb-1 block">Company</Label>
              <Input
                value={companyVal}
                onChange={(e) => setCompanyVal(e.target.value)}
                className="rounded-lg text-sm"
                placeholder="Optional"
              />
            </div>
            <div>
              <Label className="text-[11px] mb-1 block">Role</Label>
              <Input
                value={roleVal}
                onChange={(e) => setRoleVal(e.target.value)}
                className="rounded-lg text-sm"
                placeholder="Optional"
              />
            </div>
          </div>

          <div className="rounded-lg border p-3 max-h-24 overflow-auto text-[11px] leading-relaxed bg-card text-muted-foreground">
            {content.slice(0, 500)}{content.length > 500 ? "..." : ""}
          </div>
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        <DialogFooter className="pt-1">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs">
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving || saved || !title.trim()}
            className="text-xs"
          >
            {saved ? "Saved!" : saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
