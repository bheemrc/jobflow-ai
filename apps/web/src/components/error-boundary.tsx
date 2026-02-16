"use client";

import React, { Component } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  label?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[ErrorBoundary${this.props.label ? `: ${this.props.label}` : ""}]`, error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 my-2">
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-lg flex items-center justify-center text-sm shrink-0 bg-destructive/10">
              ⚠️
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-[12px] font-bold mb-1 text-foreground">
                {this.props.label ? `${this.props.label} Error` : "Something went wrong"}
              </h4>
              <p className="text-[11px] mb-2 text-muted-foreground">
                {this.state.error?.message || "An unexpected error occurred in this component."}
              </p>
              <Button variant="outline" size="sm" onClick={this.handleRetry} className="text-[11px] h-7">
                Try Again
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/** Inline error boundary for smaller components */
export function InlineError({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-destructive/15 bg-destructive/5 px-3 py-2 text-[10px] text-destructive flex items-center gap-2">
      <span>⚠️</span>
      <span>{message}</span>
    </div>
  );
}

/** Offline indicator bar */
export function OfflineBar({ visible }: { visible: boolean }) {
  if (!visible) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-destructive text-destructive-foreground shadow-lg animate-scale-in">
      <div className="flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full animate-pulse bg-white" />
        <span className="text-[11px] font-semibold">
          Connection lost — attempting to reconnect...
        </span>
      </div>
    </div>
  );
}
