"use client";

import { useState } from "react";
import type { BotState } from "@/lib/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";

interface BotConfigModalProps {
  bot: BotState;
  onClose: () => void;
  onSave: (config: Record<string, unknown>) => void;
}

export default function BotConfigModal({ bot, onClose, onSave }: BotConfigModalProps) {
  const [model, setModel] = useState(bot.config.model || "default");
  const [temperature, setTemperature] = useState(bot.config.temperature ?? 0.5);
  const [timeoutMinutes, setTimeoutMinutes] = useState(bot.config.timeout_minutes ?? 10);
  const [scheduleType, setScheduleType] = useState(bot.config.schedule?.type || "interval");
  const [scheduleHours, setScheduleHours] = useState(bot.config.schedule?.hours ?? 6);
  const [scheduleHour, setScheduleHour] = useState(bot.config.schedule?.hour ?? 8);
  const [scheduleMinute, setScheduleMinute] = useState(bot.config.schedule?.minute ?? 0);

  const handleSave = () => {
    onSave({
      model,
      temperature,
      timeout_minutes: timeoutMinutes,
      schedule: scheduleType === "interval"
        ? { type: "interval", hours: scheduleHours }
        : { type: "cron", hour: scheduleHour, minute: scheduleMinute },
    });
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-[440px] max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>Configure {bot.display_name}</DialogTitle>
          <DialogDescription>{bot.description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Model */}
          <div>
            <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Model Tier
            </Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger className="mt-1.5">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="fast">Fast (GPT-4o-mini)</SelectItem>
                <SelectItem value="default">Default (GPT-4o)</SelectItem>
                <SelectItem value="strong">Strong (GPT-4o)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Temperature */}
          <div>
            <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Temperature: {temperature.toFixed(1)}
            </Label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full mt-1.5 accent-primary"
            />
          </div>

          {/* Timeout */}
          <div>
            <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Timeout (minutes)
            </Label>
            <Input
              type="number"
              min={1}
              max={60}
              value={timeoutMinutes}
              onChange={(e) => setTimeoutMinutes(parseInt(e.target.value) || 10)}
              className="mt-1.5 text-sm"
            />
          </div>

          {/* Schedule */}
          <div>
            <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Schedule Type
            </Label>
            <Select value={scheduleType} onValueChange={setScheduleType}>
              <SelectTrigger className="mt-1.5">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="interval">Interval</SelectItem>
                <SelectItem value="cron">Daily (Cron)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {scheduleType === "interval" ? (
            <div>
              <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Every N hours
              </Label>
              <Input
                type="number"
                min={1}
                max={48}
                value={scheduleHours}
                onChange={(e) => setScheduleHours(parseInt(e.target.value) || 6)}
                className="mt-1.5 text-sm"
              />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Hour (0-23)
                </Label>
                <Input
                  type="number"
                  min={0}
                  max={23}
                  value={scheduleHour}
                  onChange={(e) => setScheduleHour(parseInt(e.target.value) || 0)}
                  className="mt-1.5 text-sm"
                />
              </div>
              <div>
                <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Minute (0-59)
                </Label>
                <Input
                  type="number"
                  min={0}
                  max={59}
                  value={scheduleMinute}
                  onChange={(e) => setScheduleMinute(parseInt(e.target.value) || 0)}
                  className="mt-1.5 text-sm"
                />
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} className="text-xs">
            Cancel
          </Button>
          <Button onClick={handleSave} className="text-xs">
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
