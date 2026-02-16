"use client";

import { useEffect, useCallback, useRef } from "react";

interface KeyboardShortcutOptions {
  onNavigateDown?: () => void;
  onNavigateUp?: () => void;
  onReply?: () => void;
  onVoteUp?: () => void;
  onVoteDown?: () => void;
  onSearch?: () => void;
  onCompose?: () => void;
  onEscape?: () => void;
  onHelp?: () => void;
}

export function useKeyboardShortcuts(options: KeyboardShortcutOptions) {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't fire when typing in inputs
    const target = e.target as HTMLElement;
    if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
      if (e.key === "Escape") {
        (target as HTMLInputElement).blur();
        optionsRef.current.onEscape?.();
      }
      return;
    }

    // Don't intercept browser shortcuts (Cmd+C, Ctrl+V, etc.)
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    switch (e.key) {
      case "j":
        e.preventDefault();
        optionsRef.current.onNavigateDown?.();
        break;
      case "k":
        e.preventDefault();
        optionsRef.current.onNavigateUp?.();
        break;
      case "r":
        e.preventDefault();
        optionsRef.current.onReply?.();
        break;
      case "a":
        e.preventDefault();
        optionsRef.current.onVoteUp?.();
        break;
      case "z":
        e.preventDefault();
        optionsRef.current.onVoteDown?.();
        break;
      case "/":
        e.preventDefault();
        optionsRef.current.onSearch?.();
        break;
      case "c":
        e.preventDefault();
        optionsRef.current.onCompose?.();
        break;
      case "Escape":
        optionsRef.current.onEscape?.();
        break;
      case "?":
        e.preventDefault();
        optionsRef.current.onHelp?.();
        break;
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}
