"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { AvailableTool, BotTemplate } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const INTEGRATION_OPTIONS = [
  {
    id: "telegram",
    name: "Telegram",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
        <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
      </svg>
    ),
    fields: [
      { key: "bot_token", label: "Bot Token", placeholder: "123456:ABC-DEF...", type: "password" },
      { key: "chat_id", label: "Chat ID", placeholder: "-100123456789", type: "text" },
    ],
  },
  {
    id: "slack",
    name: "Slack",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
      </svg>
    ),
    fields: [
      { key: "webhook_url", label: "Webhook URL", placeholder: "https://hooks.slack.com/services/...", type: "url" },
    ],
  },
  {
    id: "discord",
    name: "Discord",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
        <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z" />
      </svg>
    ),
    fields: [
      { key: "webhook_url", label: "Webhook URL", placeholder: "https://discord.com/api/webhooks/...", type: "url" },
    ],
  },
  {
    id: "webhook",
    name: "Custom Webhook",
    icon: (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
      </svg>
    ),
    fields: [
      { key: "url", label: "Endpoint URL", placeholder: "https://your-api.com/webhook", type: "url" },
      { key: "secret", label: "Secret (optional)", placeholder: "webhook-secret-123", type: "password" },
    ],
  },
  {
    id: "whatsapp",
    name: "WhatsApp",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
      </svg>
    ),
    fields: [
      { key: "phone_id", label: "Phone Number ID", placeholder: "15550001234", type: "text" },
      { key: "access_token", label: "Access Token", placeholder: "EAA...", type: "password" },
    ],
  },
];

const TOOL_CATEGORIES: Record<string, { label: string; colorClass: string }> = {
  resume: { label: "Resume", colorClass: "text-primary" },
  jobs: { label: "Jobs", colorClass: "text-success" },
  research: { label: "Research", colorClass: "text-warning" },
  leetcode: { label: "LeetCode", colorClass: "text-purple-500" },
  integrations: { label: "Integrations", colorClass: "text-pink-500" },
  other: { label: "Other", colorClass: "text-muted-foreground" },
};

const STEPS = [
  { id: "template", label: "Choose Template" },
  { id: "basics", label: "Name & Description" },
  { id: "tools", label: "Select Tools" },
  { id: "prompt", label: "Bot Instructions" },
  { id: "schedule", label: "Schedule" },
  { id: "integrations", label: "Connect" },
  { id: "review", label: "Review & Create" },
];

export default function CreateBotPage() {
  return (
    <Suspense fallback={
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin h-8 w-8 rounded-full border-[3px] border-muted border-t-primary" />
      </div>
    }>
      <CreateBotPageInner />
    </Suspense>
  );
}

function CreateBotPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState(0);
  const [templates, setTemplates] = useState<BotTemplate[]>([]);
  const [availableTools, setAvailableTools] = useState<AvailableTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [botName, setBotName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("default");
  const [temperature, setTemperature] = useState(0.5);
  const [scheduleType, setScheduleType] = useState("interval");
  const [scheduleHours, setScheduleHours] = useState(6);
  const [scheduleHour, setScheduleHour] = useState(9);
  const [scheduleMinute, setScheduleMinute] = useState(0);
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [timeoutMinutes, setTimeoutMinutes] = useState(10);
  const [enabledIntegrations, setEnabledIntegrations] = useState<Set<string>>(new Set());
  const [integrationConfigs, setIntegrationConfigs] = useState<Record<string, Record<string, string>>>({});

  // Load templates and tools
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [templatesRes, toolsRes] = await Promise.allSettled([
          fetch("/api/ai/bots/templates").then((r) => r.json()),
          fetch("/api/ai/bots/tools").then((r) => r.json()),
        ]);
        if (templatesRes.status === "fulfilled") setTemplates(templatesRes.value.templates || []);
        if (toolsRes.status === "fulfilled") setAvailableTools(toolsRes.value.tools || []);
      } catch {
        // Ignore load errors
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Pre-fill from template query param
  useEffect(() => {
    const templateId = searchParams.get("template");
    if (templateId && templates.length > 0) {
      const tmpl = templates.find((t) => t.id === templateId);
      if (tmpl) {
        applyTemplate(tmpl);
        setStep(1); // Skip template selection
      }
    }
  }, [searchParams, templates]);

  const applyTemplate = (tmpl: BotTemplate) => {
    setSelectedTemplate(tmpl.id);
    setDisplayName(tmpl.name);
    setBotName(tmpl.id);
    setDescription(tmpl.description);
    setSelectedTools(tmpl.tools);
    setPrompt(tmpl.prompt);
    setModel(tmpl.model);
    setScheduleType(tmpl.schedule_type);
    if (tmpl.schedule_hours) setScheduleHours(tmpl.schedule_hours);
    if (tmpl.schedule_hour !== undefined) setScheduleHour(tmpl.schedule_hour);
    if (tmpl.schedule_minute !== undefined) setScheduleMinute(tmpl.schedule_minute);
  };

  const autoName = useCallback((display: string) => {
    return display
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, "")
      .replace(/\s+/g, "_")
      .replace(/^[^a-z]/, "b")
      .slice(0, 49);
  }, []);

  const toggleTool = (name: string) => {
    setSelectedTools((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
    );
  };

  const toggleIntegration = (id: string) => {
    setEnabledIntegrations((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setIntegrationField = (integrationId: string, key: string, value: string) => {
    setIntegrationConfigs((prev) => ({
      ...prev,
      [integrationId]: { ...prev[integrationId], [key]: value },
    }));
  };

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const integrations: Record<string, Record<string, string>> = {};
      for (const id of enabledIntegrations) {
        if (integrationConfigs[id]) {
          integrations[id] = integrationConfigs[id];
        }
      }

      const res = await fetch("/api/ai/bots/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: botName,
          display_name: displayName,
          description,
          model,
          temperature,
          max_tokens: 4096,
          tools: selectedTools,
          prompt,
          schedule_type: scheduleType,
          schedule_hours: scheduleType === "interval" ? scheduleHours : undefined,
          schedule_hour: scheduleType === "cron" ? scheduleHour : undefined,
          schedule_minute: scheduleType === "cron" ? scheduleMinute : undefined,
          requires_approval: requiresApproval,
          timeout_minutes: timeoutMinutes,
          integrations,
        }),
      });
      const data = await res.json();
      if (data.error || data.detail) {
        setError(data.error || data.detail);
        return;
      }
      router.push(`/bots/${botName}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 0: return true; // Template is optional
      case 1: return botName.length >= 2 && displayName.length >= 1;
      case 2: return selectedTools.length >= 1;
      case 3: return prompt.length >= 10;
      case 4: return true;
      case 5: return true;
      case 6: return true;
      default: return false;
    }
  };

  const toolsByCategory = availableTools.reduce<Record<string, AvailableTool[]>>((acc, tool) => {
    const cat = tool.category || "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(tool);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin h-8 w-8 rounded-full border-[3px] border-muted border-t-primary" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-[900px] mx-auto p-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8 animate-fade-in-up">
          <button
            onClick={() => router.push("/bots")}
            className="flex items-center justify-center h-9 w-9 rounded-xl transition-colors bg-muted hover:bg-accent"
          >
            <svg className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <div>
            <h1 className="text-[22px] font-bold tracking-tight text-foreground">
              Create New Bot
            </h1>
            <p className="text-sm mt-0.5 text-muted-foreground/70">
              Build a custom autonomous agent for your job search
            </p>
          </div>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-1 mb-8 overflow-x-auto pb-1">
          {STEPS.map((s, i) => (
            <button
              key={s.id}
              onClick={() => i <= step && setStep(i)}
              className="flex items-center gap-1.5 shrink-0"
            >
              <div
                className={cn(
                  "flex items-center justify-center h-6 w-6 rounded-full text-[10px] font-bold transition-all",
                  i <= step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                )}
              >
                {i < step ? (
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium hidden sm:inline",
                  i <= step ? "text-foreground" : "text-muted-foreground/70"
                )}
              >
                {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <div className={cn("w-4 h-px mx-1", i < step ? "bg-primary" : "bg-border")} />
              )}
            </button>
          ))}
        </div>

        {/* Step content */}
        <div className="animate-fade-in-up">
          {/* Step 0: Template */}
          {step === 0 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Start from a Template
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                Choose a pre-configured template or start from scratch
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                {templates.map((tmpl) => (
                  <Card
                    key={tmpl.id}
                    className={cn(
                      "cursor-pointer text-left p-4 transition-all hover:shadow-md hover:border-primary/20",
                      selectedTemplate === tmpl.id && "border-primary"
                    )}
                    onClick={() => { applyTemplate(tmpl); setStep(1); }}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex items-center justify-center h-10 w-10 rounded-xl shrink-0 bg-primary/10">
                        <svg className="h-5 w-5 text-primary" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                        </svg>
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-foreground">
                          {tmpl.name}
                        </h3>
                        <p className="text-[11px] mt-0.5 line-clamp-2 text-muted-foreground/70">
                          {tmpl.description}
                        </p>
                        <div className="flex flex-wrap gap-1 mt-2">
                          {tmpl.integrations.map((int_id) => (
                            <Badge key={int_id} variant="secondary" className="text-[9px]">
                              {int_id}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              <Card
                className="cursor-pointer p-4 text-center hover:shadow-md hover:border-primary/20 transition-all"
                onClick={() => setStep(1)}
              >
                <p className="text-sm font-medium text-muted-foreground">
                  Start from Scratch
                </p>
                <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                  Build a fully custom bot with any tools and integrations
                </p>
              </Card>
            </div>
          )}

          {/* Step 1: Basics */}
          {step === 1 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Name Your Bot
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                Give it a recognizable identity
              </p>

              <div className="space-y-4">
                <div>
                  <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Display Name
                  </Label>
                  <Input
                    type="text"
                    value={displayName}
                    onChange={(e) => {
                      setDisplayName(e.target.value);
                      if (!selectedTemplate) setBotName(autoName(e.target.value));
                    }}
                    placeholder="My Custom Bot"
                    className="mt-1.5 text-sm"
                    autoFocus
                  />
                </div>

                <div>
                  <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Bot ID <span className="normal-case">(auto-generated)</span>
                  </Label>
                  <Input
                    type="text"
                    value={botName}
                    onChange={(e) => setBotName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                    placeholder="my_custom_bot"
                    className="mt-1.5 text-sm data-mono"
                  />
                  <p className="text-[10px] mt-1 text-muted-foreground/70">
                    Lowercase letters, numbers, and underscores only
                  </p>
                </div>

                <div>
                  <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Description
                  </Label>
                  <Textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="What does this bot do?"
                    rows={2}
                    className="mt-1.5 text-sm resize-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Model Tier
                    </Label>
                    <div className="flex gap-2 mt-1.5">
                      {(["fast", "default", "strong"] as const).map((m) => (
                        <Button
                          key={m}
                          variant={model === m ? "default" : "outline"}
                          size="sm"
                          onClick={() => setModel(m)}
                          className="flex-1 text-[11px]"
                        >
                          {m === "fast" ? "Fast" : m === "default" ? "Balanced" : "Strong"}
                        </Button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Temperature: {temperature.toFixed(1)}
                    </Label>
                    <input
                      type="range"
                      min="0"
                      max="1.5"
                      step="0.1"
                      value={temperature}
                      onChange={(e) => setTemperature(parseFloat(e.target.value))}
                      className="w-full mt-1.5 accent-primary"
                    />
                    <div className="flex justify-between text-[9px] text-muted-foreground/70">
                      <span>Precise</span>
                      <span>Creative</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Tools */}
          {step === 2 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Select Tools
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                Choose what capabilities your bot has -- {selectedTools.length} selected
              </p>

              <div className="space-y-5">
                {Object.entries(toolsByCategory).map(([category, tools]) => {
                  const catInfo = TOOL_CATEGORIES[category] || TOOL_CATEGORIES.other;
                  return (
                    <div key={category}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className={cn("h-2 w-2 rounded-full", {
                          "bg-primary": category === "resume",
                          "bg-success": category === "jobs",
                          "bg-warning": category === "research",
                          "bg-purple-500": category === "leetcode",
                          "bg-pink-500": category === "integrations",
                          "bg-muted-foreground": category === "other",
                        })} />
                        <h3 className={cn("text-xs font-semibold uppercase tracking-wider", catInfo.colorClass)}>
                          {catInfo.label}
                        </h3>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {tools.map((tool) => {
                          const isSelected = selectedTools.includes(tool.name);
                          return (
                            <button
                              key={tool.name}
                              onClick={() => toggleTool(tool.name)}
                              className={cn(
                                "text-left rounded-lg px-3 py-2.5 transition-all border",
                                isSelected
                                  ? "bg-primary/10 border-primary"
                                  : "bg-muted border-border hover:border-primary/30"
                              )}
                            >
                              <div className="flex items-center gap-2">
                                <div
                                  className={cn(
                                    "flex items-center justify-center h-4 w-4 rounded shrink-0",
                                    isSelected ? "bg-primary" : "bg-muted border"
                                  )}
                                >
                                  {isSelected && (
                                    <svg className="h-3 w-3 text-primary-foreground" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                    </svg>
                                  )}
                                </div>
                                <span className={cn("text-xs font-medium data-mono", isSelected ? "text-primary" : "text-foreground")}>
                                  {tool.name}
                                </span>
                              </div>
                              {tool.description && (
                                <p className="text-[10px] mt-1 ml-6 line-clamp-2 text-muted-foreground/70">
                                  {tool.description}
                                </p>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 3: Prompt */}
          {step === 3 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Bot Instructions
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                Tell your bot what to do. Be specific about mandatory steps and output format.
              </p>

              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={`You are an autonomous bot. Your mission is to...\n\n## Mandatory Steps\n1. Call [tool_name] to...\n2. ...\n\n## Output Format\n- **Section**: Description...`}
                rows={14}
                className="text-sm resize-y font-mono leading-relaxed"
              />
              <div className="flex items-center justify-between mt-2">
                <p className="text-[10px] text-muted-foreground/70">
                  {prompt.length}/10,000 characters
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="approval"
                    checked={requiresApproval}
                    onChange={(e) => setRequiresApproval(e.target.checked)}
                    className="accent-primary"
                  />
                  <label htmlFor="approval" className="text-[11px] text-muted-foreground">
                    Require human approval before actions
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Schedule */}
          {step === 4 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Schedule
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                How often should this bot run?
              </p>

              <div className="space-y-4">
                <div className="flex gap-3">
                  <Card
                    className={cn(
                      "flex-1 p-4 transition-all text-left cursor-pointer hover:shadow-md",
                      scheduleType === "interval" && "border-primary bg-primary/5"
                    )}
                    onClick={() => setScheduleType("interval")}
                  >
                    <h3 className={cn("text-sm font-semibold", scheduleType === "interval" ? "text-primary" : "text-foreground")}>
                      Recurring Interval
                    </h3>
                    <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                      Run every N hours
                    </p>
                  </Card>
                  <Card
                    className={cn(
                      "flex-1 p-4 transition-all text-left cursor-pointer hover:shadow-md",
                      scheduleType === "cron" && "border-primary bg-primary/5"
                    )}
                    onClick={() => setScheduleType("cron")}
                  >
                    <h3 className={cn("text-sm font-semibold", scheduleType === "cron" ? "text-primary" : "text-foreground")}>
                      Daily at Time
                    </h3>
                    <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                      Run once per day at a specific time
                    </p>
                  </Card>
                </div>

                {scheduleType === "interval" ? (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Run every
                    </Label>
                    <div className="flex items-center gap-2 mt-1.5">
                      <Input
                        type="number"
                        min={1}
                        max={168}
                        value={scheduleHours}
                        onChange={(e) => setScheduleHours(parseInt(e.target.value) || 1)}
                        className="w-20 text-center text-sm"
                      />
                      <span className="text-sm text-muted-foreground">hours</span>
                    </div>
                    <div className="flex gap-2 mt-3">
                      {[1, 4, 6, 12, 24].map((h) => (
                        <Button
                          key={h}
                          variant={scheduleHours === h ? "default" : "outline"}
                          size="sm"
                          onClick={() => setScheduleHours(h)}
                          className="text-[11px]"
                        >
                          {h}h
                        </Button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Run daily at
                    </Label>
                    <div className="flex items-center gap-2 mt-1.5">
                      <Input
                        type="number"
                        min={0}
                        max={23}
                        value={scheduleHour}
                        onChange={(e) => setScheduleHour(parseInt(e.target.value) || 0)}
                        className="w-16 text-center text-sm"
                      />
                      <span className="text-base font-bold text-muted-foreground/70">:</span>
                      <Input
                        type="number"
                        min={0}
                        max={59}
                        value={scheduleMinute}
                        onChange={(e) => setScheduleMinute(parseInt(e.target.value) || 0)}
                        className="w-16 text-center text-sm"
                      />
                      <span className="text-sm text-muted-foreground">UTC</span>
                    </div>
                  </div>
                )}

                <div>
                  <Label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Timeout: {timeoutMinutes} minutes
                  </Label>
                  <input
                    type="range"
                    min="1"
                    max="60"
                    value={timeoutMinutes}
                    onChange={(e) => setTimeoutMinutes(parseInt(e.target.value))}
                    className="w-full mt-1.5 accent-primary"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 5: Integrations */}
          {step === 5 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Connect Integrations
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                Optional: connect external services to send notifications and data
              </p>

              <div className="space-y-3">
                {INTEGRATION_OPTIONS.map((integration) => {
                  const isEnabled = enabledIntegrations.has(integration.id);
                  return (
                    <Card key={integration.id} className="overflow-hidden">
                      <button
                        onClick={() => toggleIntegration(integration.id)}
                        className={cn("w-full flex items-center gap-3 p-4 transition-all", isEnabled && "bg-primary/5")}
                      >
                        <div
                          className={cn(
                            "flex items-center justify-center h-9 w-9 rounded-lg shrink-0",
                            isEnabled ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                          )}
                        >
                          {integration.icon}
                        </div>
                        <div className="flex-1 text-left">
                          <h3 className="text-sm font-semibold text-foreground">
                            {integration.name}
                          </h3>
                        </div>
                        <Switch checked={isEnabled} />
                      </button>

                      {isEnabled && (
                        <div className="px-4 pb-4 pt-1 space-y-3 border-t">
                          {integration.fields.map((field) => (
                            <div key={field.key}>
                              <Label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                                {field.label}
                              </Label>
                              <Input
                                type={field.type}
                                value={integrationConfigs[integration.id]?.[field.key] || ""}
                                onChange={(e) => setIntegrationField(integration.id, field.key, e.target.value)}
                                placeholder={field.placeholder}
                                className="mt-1 h-8 text-xs data-mono"
                              />
                            </div>
                          ))}
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 6: Review */}
          {step === 6 && (
            <div>
              <h2 className="text-base font-semibold mb-1 text-foreground">
                Review & Create
              </h2>
              <p className="text-xs mb-5 text-muted-foreground/70">
                Confirm your bot configuration
              </p>

              {error && (
                <Card className="p-3 mb-4 bg-destructive/10 border-destructive">
                  <p className="text-xs font-medium text-destructive">{error}</p>
                </Card>
              )}

              <div className="space-y-3">
                <Card className="p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex items-center justify-center h-12 w-12 rounded-xl shrink-0 bg-primary/10">
                      <svg className="h-6 w-6 text-primary" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-[15px] font-bold text-foreground">{displayName}</h3>
                      <p className="text-[11px] data-mono text-muted-foreground/70">{botName}</p>
                      <p className="text-xs mt-1 text-muted-foreground">{description}</p>
                    </div>
                  </div>
                </Card>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "Model", value: model },
                    { label: "Tools", value: String(selectedTools.length) },
                    { label: "Schedule", value: scheduleType === "interval" ? `Every ${scheduleHours}h` : `${String(scheduleHour).padStart(2, "0")}:${String(scheduleMinute).padStart(2, "0")} UTC` },
                    { label: "Integrations", value: String(enabledIntegrations.size) },
                  ].map((item) => (
                    <Card key={item.label} className="p-3">
                      <p className="text-[9px] uppercase tracking-wider mb-0.5 text-muted-foreground/70">{item.label}</p>
                      <p className="text-sm font-semibold text-foreground">{item.value}</p>
                    </Card>
                  ))}
                </div>

                <Card className="p-4">
                  <p className="text-[10px] uppercase tracking-wider mb-2 font-medium text-muted-foreground/70">Tools</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTools.map((t) => (
                      <Badge key={t} variant="secondary" className="text-[10px] data-mono">
                        {t}
                      </Badge>
                    ))}
                  </div>
                </Card>

                {enabledIntegrations.size > 0 && (
                  <Card className="p-4">
                    <p className="text-[10px] uppercase tracking-wider mb-2 font-medium text-muted-foreground/70">Connected</p>
                    <div className="flex gap-2">
                      {Array.from(enabledIntegrations).map((id) => {
                        const intg = INTEGRATION_OPTIONS.find((i) => i.id === id);
                        return (
                          <div
                            key={id}
                            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted"
                          >
                            <span className="text-primary">{intg?.icon}</span>
                            <span className="text-[11px] font-medium text-muted-foreground">{intg?.name}</span>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}

                <Card className="p-4">
                  <p className="text-[10px] uppercase tracking-wider mb-2 font-medium text-muted-foreground/70">Prompt Preview</p>
                  <pre className="text-[11px] whitespace-pre-wrap max-h-[200px] overflow-auto text-muted-foreground font-mono">
                    {prompt.slice(0, 500)}{prompt.length > 500 && "..."}
                  </pre>
                </Card>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8 pb-6">
          <Button
            variant="ghost"
            onClick={() => setStep(Math.max(0, step - 1))}
            className="text-xs"
            style={{ visibility: step === 0 ? "hidden" : "visible" }}
          >
            Back
          </Button>

          {step < STEPS.length - 1 ? (
            <Button
              onClick={() => setStep(step + 1)}
              disabled={!canProceed()}
              className="text-xs font-semibold"
            >
              Continue
            </Button>
          ) : (
            <Button
              onClick={handleCreate}
              disabled={creating || !canProceed()}
              className="text-xs font-semibold gap-2"
            >
              {creating ? (
                <>
                  <div className="animate-spin h-3.5 w-3.5 rounded-full border-2 border-primary-foreground/20 border-t-primary-foreground" />
                  Creating...
                </>
              ) : (
                "Create Bot"
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
