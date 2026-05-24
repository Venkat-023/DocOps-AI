import { cn } from "@/lib/utils";

type Color = "brand" | "warning" | "success" | "info" | "teal" | "muted";

const colorMap: Record<Color, { on: string; off: string }> = {
  brand: { on: "bg-brand-light text-brand-dark border-brand-border", off: "bg-card text-muted-foreground border-border hover:text-foreground" },
  warning: { on: "bg-warning/15 text-warning border-warning/40", off: "bg-card text-muted-foreground border-border hover:text-foreground" },
  success: { on: "bg-success/15 text-success border-success/40", off: "bg-card text-muted-foreground border-border hover:text-foreground" },
  info: { on: "bg-info/15 text-info border-info/40", off: "bg-card text-muted-foreground border-border hover:text-foreground" },
  teal: { on: "bg-teal/15 text-teal border-teal/40", off: "bg-card text-muted-foreground border-border hover:text-foreground" },
  muted: { on: "bg-accent text-foreground border-border", off: "bg-card text-muted-foreground border-border hover:text-foreground" },
};

export function Pill({
  active,
  onClick,
  children,
  color = "brand",
  type = "button",
}: {
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
  color?: Color;
  type?: "button" | "submit";
}) {
  const c = colorMap[color];
  return (
    <button
      type={type}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill border px-3 py-1 text-xs font-medium transition-colors duration-150",
        active ? c.on : c.off,
      )}
    >
      {children}
    </button>
  );
}
