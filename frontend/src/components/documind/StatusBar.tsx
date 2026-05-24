import { cn } from "@/lib/utils";
import type { DocStatus } from "@/hooks/useDocGen";

export function StatusBar({
  status,
  tokens,
  fileInfo,
}: {
  status: DocStatus;
  tokens: number;
  fileInfo?: string;
}) {
  const isStreaming = status === "generating";
  const isError = status === "error";
  const dotColor = isError ? "bg-destructive" : isStreaming ? "bg-success" : "bg-muted-foreground/40";
  const label =
    status === "generating"
      ? `Streaming · ${tokens} tokens · claude-sonnet-4`
      : status === "fetching"
        ? "Fetching source…"
        : status === "done"
          ? `Done · ${tokens} tokens · claude-sonnet-4`
          : status === "error"
            ? "Error"
            : "Idle";
  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border bg-card px-4 font-mono text-[11px] text-muted-foreground">
      <div className="flex items-center gap-2">
        <span className={cn("h-1.5 w-1.5 rounded-full", dotColor, isStreaming && "pulse-dot")} />
        <span>{label}</span>
      </div>
      <span className="truncate">{fileInfo ?? "no source loaded"}</span>
    </footer>
  );
}
