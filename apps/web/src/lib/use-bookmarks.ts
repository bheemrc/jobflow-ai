"use client";

import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY = "nexus_bookmarks";

export function useBookmarks() {
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<number>>(new Set());

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const ids = JSON.parse(stored) as number[];
        setBookmarkedIds(new Set(ids));
      }
    } catch {}
  }, []);

  // Save to localStorage on change
  const persist = useCallback((ids: Set<number>) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
    } catch {}
  }, []);

  const toggleBookmark = useCallback((postId: number) => {
    setBookmarkedIds((prev) => {
      const next = new Set(prev);
      if (next.has(postId)) {
        next.delete(postId);
      } else {
        next.add(postId);
      }
      persist(next);
      return next;
    });
  }, [persist]);

  const isBookmarked = useCallback((postId: number) => bookmarkedIds.has(postId), [bookmarkedIds]);

  return { bookmarkedIds, toggleBookmark, isBookmarked, count: bookmarkedIds.size };
}
