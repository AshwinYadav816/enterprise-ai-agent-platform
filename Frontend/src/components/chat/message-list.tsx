"use client";

import { ArrowDown, Loader2 } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

const NEAR_BOTTOM_PX = 120;

type MessageListProps = {
  children: React.ReactNode;
  hasEarlier: boolean;
  loadingEarlier: boolean;
  onLoadEarlier: () => Promise<unknown>;
};

/**
 * Scrolling message column. Follows new content only while the reader is near the bottom
 * (otherwise "Jump to latest"); "Load earlier" keeps the reading position.
 */
export function MessageList({
  children,
  hasEarlier,
  loadingEarlier,
  onLoadEarlier,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [showJump, setShowJump] = useState(false);

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  // New tokens / messages / cards change the content height: follow them if near the bottom.
  useLayoutEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    const observer = new ResizeObserver(() => {
      if (nearBottom.current) scrollToBottom();
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [scrollToBottom]);

  useEffect(() => scrollToBottom(), [scrollToBottom]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    nearBottom.current = distance < NEAR_BOTTOM_PX;
    setShowJump(!nearBottom.current);
  };

  const loadEarlier = async () => {
    const el = scrollRef.current;
    const before = el?.scrollHeight ?? 0;
    await onLoadEarlier();
    requestAnimationFrame(() => {
      if (el) el.scrollTop += el.scrollHeight - before; // keep the same message in view
    });
  };

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto">
        <div ref={contentRef} className="mx-auto w-full max-w-[760px] px-4 py-6 md:px-6">
          {hasEarlier && (
            <div className="mb-6 flex justify-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadEarlier()}
                disabled={loadingEarlier}
              >
                {loadingEarlier && <Loader2 className="animate-spin" aria-hidden />}
                Load earlier messages
              </Button>
            </div>
          )}
          <div className="space-y-8">{children}</div>
        </div>
      </div>
      {showJump && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => scrollToBottom(true)}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-card shadow-pop"
        >
          <ArrowDown /> Jump to latest
        </Button>
      )}
    </div>
  );
}
