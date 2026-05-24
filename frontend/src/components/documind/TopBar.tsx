import { FileText } from "lucide-react";

export function TopBar() {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-brand text-primary-foreground">
          <FileText className="h-3.5 w-3.5" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-foreground">DocuMind</span>
        <span className="ml-2 rounded-pill border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
          beta
        </span>
      </div>
      <nav className="flex items-center gap-1 text-xs text-muted-foreground">
        <button className="rounded-md px-2.5 py-1 transition-colors duration-150 hover:text-foreground">Docs</button>
        <button className="rounded-md px-2.5 py-1 transition-colors duration-150 hover:text-foreground">Changelog</button>
        <button className="rounded-md border border-border px-2.5 py-1 font-medium text-foreground transition-colors duration-150 hover:bg-accent">
          Sign in
        </button>
      </nav>
    </header>
  );
}
