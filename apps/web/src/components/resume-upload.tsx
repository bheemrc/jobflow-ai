"use client";

import { useState, useRef } from "react";
import { FileUp, CheckCircle, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";

interface ResumeUploadProps {
  onResumeId?: (id: string) => void;
  onGetStrategy?: () => void;
  /** When true, always show the upload drop zone (used for "Change Resume" flow). */
  replaceMode?: boolean;
}

export default function ResumeUpload({ onResumeId, onGetStrategy, replaceMode }: ResumeUploadProps) {
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [showPaste, setShowPaste] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  // In replaceMode, always show the upload UI regardless of resumeId
  const showUploadUI = replaceMode || (!resumeId && !loading);
  const showLoadedUI = !replaceMode && resumeId && !loading;

  async function handleUpload(file?: File, text?: string) {
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      if (file) {
        formData.append("file", file);
        setFileName(file.name);
      } else if (text) {
        formData.append("text", text);
        setFileName("Pasted text");
      } else {
        return;
      }

      const res = await fetch("/api/ai/parse-resume", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Upload failed");
      }

      const data = await res.json();
      setResumeId(data.resume_id);
      onResumeId?.(data.resume_id);

      setShowPaste(false);
      setPastedText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {showUploadUI && !loading && (
        <div className="space-y-3">
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileRef.current?.click()}
            className="flex flex-col items-center justify-center gap-2 rounded-xl px-4 py-8 cursor-pointer transition-all duration-200 border-2 border-dashed border-border bg-muted hover:border-primary hover:bg-primary/5"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent">
              <FileUp className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-[12px] font-medium text-muted-foreground">
              Drop PDF or click to upload
            </p>
            <p className="text-[10px] text-muted-foreground/70">PDF, TXT supported</p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          <div className="flex items-center gap-2">
            <Separator className="flex-1" />
            <span className="text-xs font-medium text-muted-foreground uppercase">or</span>
            <Separator className="flex-1" />
          </div>

          {!showPaste ? (
            <Button
              variant="ghost"
              onClick={() => setShowPaste(true)}
              className="w-full rounded-xl py-2.5 text-[12px] font-medium"
            >
              Paste resume text
            </Button>
          ) : (
            <div className="space-y-2">
              <Textarea
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                rows={6}
                placeholder="Paste your resume text here..."
                className="w-full rounded-xl px-3 py-2 text-[12px]"
                autoFocus
              />
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => { setShowPaste(false); setPastedText(""); }}
                  className="flex-1 rounded-xl py-2 text-[12px] font-medium"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => handleUpload(undefined, pastedText)}
                  disabled={!pastedText.trim()}
                  className="flex-1 rounded-xl py-2 text-[12px]"
                >
                  Process
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center gap-3 py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div className="text-center">
            <p className="text-[12px] font-medium text-foreground">Processing resume...</p>
            <p className="text-[10px] mt-1 text-muted-foreground">Extracting text & generating profile</p>
          </div>
        </div>
      )}

      {showLoadedUI && (
        <>
          <div className="flex items-center justify-between rounded-xl px-3 py-2.5 bg-success/10 border border-success/20">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-success" />
              <div>
                <p className="text-[12px] font-medium text-success">Resume loaded</p>
                {fileName && <p className="text-[10px] text-success/70">{fileName}</p>}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-destructive"
              onClick={() => {
                setResumeId(null);
                setFileName(null);
              }}
              title="Remove resume"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>

          {onGetStrategy && (
            <Button
              onClick={onGetStrategy}
              className="w-full rounded-xl py-2.5 text-[12px]"
            >
              Get My Job Search Strategy
            </Button>
          )}

          <Button
            variant="ghost"
            onClick={() => {
              setResumeId(null);
              setFileName(null);
            }}
            className="w-full rounded-xl py-2.5 text-[12px] font-medium"
          >
            Upload different resume
          </Button>
        </>
      )}

      {error && (
        <div className="rounded-xl px-3 py-2.5 bg-destructive/10 border border-destructive/20">
          <p className="text-[12px] text-destructive">{error}</p>
        </div>
      )}
    </div>
  );
}
