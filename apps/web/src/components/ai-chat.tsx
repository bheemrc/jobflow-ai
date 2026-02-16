"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, RotateCcw, ChevronDown, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const QUICK_PROMPTS = [
  "Find me remote software engineering jobs",
  "What roles match my resume?",
  "Suggest alternative job titles",
  "Help me improve my search",
];

export default function AIChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>(QUICK_PROMPTS);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMsg: ChatMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        const res = await fetch("/api/ai/coach", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            session_id: conversationId,
          }),
        });

        if (!res.ok) {
          throw new Error(`AI service error (${res.status})`);
        }

        const data = await res.json();
        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: data.response || "No response received.",
        };
        setMessages((prev) => [...prev, assistantMsg]);
        if (data.session_id) setConversationId(data.session_id);
        if (data.suggestions?.length) setSuggestions(data.suggestions);
      } catch (err) {
        const errorMsg: ChatMessage = {
          role: "assistant",
          content:
            err instanceof Error
              ? `Error: ${err.message}`
              : "Failed to reach AI service. Make sure it's running on port 8002.",
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setLoading(false);
      }
    },
    [conversationId, loading]
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  if (!open) {
    return (
      <Button
        onClick={() => setOpen(true)}
        size="icon"
        className="fixed bottom-6 right-6 z-50 h-14 w-14 rounded-full shadow-lg"
        title="Open AI Chat"
      >
        <MessageSquare className="h-6 w-6" />
      </Button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex w-96 max-h-[70vh] flex-col rounded-lg border bg-background shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">JobBot AI</h3>
          <p className="text-xs text-muted-foreground">Career advisor</p>
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => {
              setMessages([]);
              setConversationId(null);
              setSuggestions(QUICK_PROMPTS);
            }}
            title="New conversation"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setOpen(false)}
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[200px] max-h-[45vh]">
        {messages.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-8">
            Ask me anything about your job search!
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}
          >
            <div
              className={cn(
                "max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              )}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
              Thinking...
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Quick suggestions */}
      {messages.length === 0 && (
        <div className="border-t px-4 py-2">
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => sendMessage(s)}
                className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t p-3">
        <div className="flex gap-2">
          <Input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about jobs, resume tips..."
            className="flex-1 text-sm"
            disabled={loading}
          />
          <Button
            type="submit"
            size="sm"
            disabled={loading || !input.trim()}
          >
            <Send className="h-4 w-4 mr-1" />
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}
