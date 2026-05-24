import { cn } from "@/lib/utils";

export function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <label className="flex flex-1 cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5 transition-colors duration-150 hover:border-brand-border">
      <div className="min-w-0">
        <div className="text-xs font-medium text-foreground">{label}</div>
        {hint && <div className="mt-0.5 truncate text-[10px] text-muted-foreground">{hint}</div>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full transition-colors duration-150",
          checked ? "bg-brand" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform duration-150",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </button>
    </label>
  );
}
