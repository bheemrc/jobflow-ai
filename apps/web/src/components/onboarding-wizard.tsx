"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import ResumeUpload from "@/components/resume-upload";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { FileUp, MapPin, Search, GraduationCap, Sparkles } from "lucide-react";

const ROLE_SUGGESTIONS = [
  "Software Engineer",
  "Frontend Developer",
  "Backend Developer",
  "Full Stack Developer",
  "Data Scientist",
  "Product Manager",
  "DevOps Engineer",
  "UX Designer",
  "Machine Learning Engineer",
  "Engineering Manager",
];

export default function OnboardingWizard() {
  const [step, setStep] = useState(0);
  const setOnboardingComplete = useAppStore((s) => s.setOnboardingComplete);
  const setUserPreferredRole = useAppStore((s) => s.setUserPreferredRole);
  const setUserPreferredLocation = useAppStore((s) => s.setUserPreferredLocation);
  const setUserWantsRemote = useAppStore((s) => s.setUserWantsRemote);

  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [remote, setRemote] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<string[]>([]);

  function handleRoleChange(value: string) {
    setRole(value);
    if (value.trim().length > 0) {
      const filtered = ROLE_SUGGESTIONS.filter((s) =>
        s.toLowerCase().includes(value.toLowerCase())
      ).slice(0, 5);
      setFilteredSuggestions(filtered);
    } else {
      setFilteredSuggestions([]);
    }
  }

  function handleNext() {
    if (step === 1) {
      setUserPreferredRole(role);
      setUserPreferredLocation(location);
      setUserWantsRemote(remote);
    }
    setStep((s) => s + 1);
  }

  function handleComplete() {
    setOnboardingComplete(true);
  }

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={cn(
                "h-2 rounded-full transition-all duration-300",
                step === i ? "w-8" : "w-2",
                step >= i ? "bg-primary" : "bg-border"
              )}
            />
          ))}
        </div>

        {/* Step 0: Upload Resume */}
        {step === 0 && (
          <div className="animate-fade-in-up">
            <Card className="p-8">
              <div className="relative z-10 text-center mb-6">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
                  <FileUp className="h-7 w-7 text-primary" />
                </div>
                <h2 className="text-lg font-bold mb-1 text-foreground">
                  Upload Your Resume
                </h2>
                <p className="text-[13px] text-muted-foreground/70">
                  This helps us match jobs and tailor your preparation
                </p>
              </div>

              <div className="relative z-10">
                <ResumeUpload onResumeId={() => handleNext()} />
              </div>

              <Button
                variant="ghost"
                onClick={handleNext}
                className="relative z-10 mt-4 w-full text-center text-[12px] font-medium text-muted-foreground/70 hover:text-muted-foreground"
              >
                Skip for now
              </Button>
            </Card>
          </div>
        )}

        {/* Step 1: Job Preferences */}
        {step === 1 && (
          <div className="animate-fade-in-up">
            <Card className="p-8">
              <div className="relative z-10 text-center mb-6">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-green-500/10 border border-green-500/20">
                  <MapPin className="h-7 w-7 text-green-400" />
                </div>
                <h2 className="text-lg font-bold mb-1 text-foreground">
                  Job Preferences
                </h2>
                <p className="text-[13px] text-muted-foreground/70">
                  What kind of roles are you looking for?
                </p>
              </div>

              <div className="relative z-10 space-y-4">
                {/* Role */}
                <div>
                  <Label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-muted-foreground/70">
                    Target Role
                  </Label>
                  <Input
                    type="text"
                    value={role}
                    onChange={(e) => handleRoleChange(e.target.value)}
                    placeholder="e.g. Software Engineer"
                    className="rounded-xl px-4 py-3 text-sm h-auto"
                  />
                  {filteredSuggestions.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {filteredSuggestions.map((s) => (
                        <button
                          key={s}
                          onClick={() => { setRole(s); setFilteredSuggestions([]); }}
                          className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all bg-muted text-muted-foreground border border-border hover:bg-accent"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Location */}
                <div>
                  <Label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-muted-foreground/70">
                    Location
                  </Label>
                  <Input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. San Francisco, New York"
                    className="rounded-xl px-4 py-3 text-sm h-auto"
                  />
                </div>

                {/* Remote toggle */}
                <label className="flex items-center gap-3 cursor-pointer rounded-xl px-4 py-3 transition-colors bg-muted border border-border hover:bg-accent">
                  <Checkbox
                    checked={remote}
                    onCheckedChange={(checked) => setRemote(checked === true)}
                    className="h-5 w-5 rounded-md"
                  />
                  <span className={cn(
                    "text-[13px] font-medium",
                    remote ? "text-foreground" : "text-muted-foreground"
                  )}>
                    Open to remote work
                  </span>
                </label>
              </div>

              <Button
                onClick={handleNext}
                className="relative z-10 mt-6 w-full rounded-xl py-3 text-sm font-semibold h-auto"
              >
                Continue
              </Button>
            </Card>
          </div>
        )}

        {/* Step 2: Quick Tour */}
        {step === 2 && (
          <div className="animate-fade-in-up">
            <div className="text-center mb-6">
              <h2 className="text-lg font-bold mb-1 text-foreground">
                You&apos;re all set!
              </h2>
              <p className="text-[13px] text-muted-foreground/70">
                Here&apos;s what you can do with JobFlow AI
              </p>
            </div>

            <div className="space-y-3">
              {[
                {
                  title: "Find Jobs",
                  desc: "Search across multiple job boards with AI-powered matching",
                  icon: Search,
                  iconColor: "text-blue-400",
                  iconBg: "bg-blue-500/10",
                },
                {
                  title: "Prepare",
                  desc: "Get interview materials, coding practice, and study guides",
                  icon: GraduationCap,
                  iconColor: "text-green-400",
                  iconBg: "bg-green-500/10",
                },
                {
                  title: "AI Coach",
                  desc: "Get personalized career advice, resume reviews, and strategy",
                  icon: Sparkles,
                  iconColor: "text-violet-400",
                  iconBg: "bg-violet-500/10",
                },
              ].map((feature) => {
                const Icon = feature.icon;
                return (
                  <Card key={feature.title} className="p-4">
                    <div className="relative z-10 flex items-center gap-4 w-full">
                      <div className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
                        feature.iconBg
                      )}>
                        <Icon className={cn("w-5 h-5", feature.iconColor)} />
                      </div>
                      <div>
                        <p className="text-[13px] font-semibold text-foreground">
                          {feature.title}
                        </p>
                        <p className="text-[11px] text-muted-foreground/70">
                          {feature.desc}
                        </p>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>

            <Button
              onClick={handleComplete}
              className="mt-6 w-full rounded-xl py-3 text-sm font-semibold h-auto"
            >
              Get Started
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
