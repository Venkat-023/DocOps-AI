import { useState } from "react";
import { Github, Upload, ClipboardPaste, FileCode2, CheckCircle2, Loader2, ArrowRight } from "lucide-react";
import { Pill } from "./Pill";
import { Toggle } from "./Toggle";
import { CodePreview } from "./CodePreview";
import { FORMAT_OPTIONS, type FormatId } from "@/lib/constants";
import type { DocStatus, Symbols } from "@/hooks/useDocGen";
import { cn } from "@/lib/utils";

type Tab = "github" | "upload" | "paste" | "openapi";

export function InputPanel(props: {
  status: DocStatus;
  sourceCode: string;
  sourceLabel: string;
  symbols: Symbols | null;
  error: string | null;
  formats: FormatId[];
  setFormats: (f: FormatId[]) => void;
  onboardingMode: boolean;
  setOnboardingMode: (v: boolean) => void;
  selfCritique: boolean;
  setSelfCritique: (v: boolean) => void;
  onFetchGitHub: (url: string) => void;
  onLoadPasted: (code: string, label?: string) => void;
  onGenerate: () => void;
}) {
  const [tab, setTab] = useState<Tab>("github");
  const [url, setUrl] = useState("https://github.com/vercel/swr/blob/main/src/index.ts");
  const [pasted, setPasted] = useState("");

  const fetching = props.status === "fetching";
  const generating = props.status === "generating";

  const toggleFormat = (id: FormatId) => {
    props.setFormats(
      props.formats.includes(id) ? props.formats.filter((f) => f !== id) : [...props.formats, id],
    );
  };

  const tabs: { id: Tab; label: string; icon: typeof Github }[] = [
    { id: "github", label: "GitHub URL", icon: Github },
    { id: "upload", label: "Upload", icon: Upload },
    { id: "paste", label: "Paste code", icon: ClipboardPaste },
    { id: "openapi", label: "OpenAPI", icon: FileCode2 },
  ];

  return (
    <section className="flex h-full min-h-0 flex-col border-r border-border bg-background">
      <div className="flex shrink-0 items-center gap-1 border-b border-border px-4 py-3">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-pill border px-3 py-1 text-xs font-medium transition-colors duration-150",
                active
                  ? "border-brand-border bg-brand-light text-brand-dark"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-3 w-3" />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {tab === "github" && (
          <div className="space-y-3">
            <label className="block text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              GitHub URL
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="github.com/owner/repo/blob/main/src/index.ts"
                className="flex-1 rounded-md border border-border bg-card px-3 py-2 font-mono text-xs text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/60 focus:border-brand"
              />
              <button
                onClick={() => props.onFetchGitHub(url)}
                disabled={fetching || !url}
                className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-2 text-xs font-medium text-background transition-colors duration-150 hover:bg-foreground/85 disabled:opacity-50"
              >
                {fetching ? <Loader2 className="h-3 w-3 animate-spin" /> : <ArrowRight className="h-3 w-3" />}
                Fetch
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Supports whole repos, single files (<code className="font-mono">/blob/</code>), or pull requests (
              <code className="font-mono">/pull/</code>).
            </p>
          </div>
        )}

        {tab === "upload" && (
          <label className="flex h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border bg-card text-center transition-colors duration-150 hover:border-brand-border hover:bg-brand-light/40">
            <Upload className="h-5 w-5 text-muted-foreground" />
            <div className="text-xs font-medium text-foreground">Drop a file or click to upload</div>
            <div className="text-[11px] text-muted-foreground">.ts · .js · .py · .go · .rs · .java</div>
            <input
              type="file"
              className="hidden"
              accept=".ts,.tsx,.js,.jsx,.py,.go,.rs,.java"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                f.text().then((t) => props.onLoadPasted(t, f.name));
              }}
            />
          </label>
        )}

        {tab === "paste" && (
          <div className="space-y-2">
            <textarea
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              placeholder="// Paste your code here…"
              className="h-44 w-full resize-none rounded-md border border-border bg-card p-3 font-mono text-xs text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/60 focus:border-brand"
            />
            <button
              onClick={() => props.onLoadPasted(pasted)}
              disabled={!pasted.trim()}
              className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors duration-150 hover:bg-accent disabled:opacity-50"
            >
              Load snippet
            </button>
          </div>
        )}

        {tab === "openapi" && (
          <div className="space-y-2">
            <textarea
              placeholder="Paste an OpenAPI 3.x spec (YAML or JSON)…"
              onChange={(e) => setPasted(e.target.value)}
              className="h-44 w-full resize-none rounded-md border border-border bg-card p-3 font-mono text-xs text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/60 focus:border-brand"
            />
            <button
              onClick={() => props.onLoadPasted(pasted, "openapi.yaml")}
              disabled={!pasted.trim()}
              className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors duration-150 hover:bg-accent disabled:opacity-50"
            >
              Load spec
            </button>
          </div>
        )}

        {props.error && (
          <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {props.error}
          </div>
        )}

        {props.sourceCode && (
          <div className="mt-5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                <span className="font-mono text-foreground">{props.sourceLabel}</span>
              </div>
              {props.symbols && (
                <span className="rounded-pill border border-success/30 bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
                  {props.symbols.lineCount} lines · {props.symbols.functions} fns · {props.symbols.classes} classes
                </span>
              )}
            </div>
            <CodePreview code={props.sourceCode} language={props.symbols?.language ?? "TypeScript"} />
          </div>
        )}

        <div className="mt-6 space-y-2">
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Output formats
          </div>
          <div className="flex flex-wrap gap-1.5">
            {FORMAT_OPTIONS.map((f) => (
              <Pill
                key={f.id}
                color={f.color as never}
                active={props.formats.includes(f.id as FormatId)}
                onClick={() => toggleFormat(f.id as FormatId)}
              >
                {f.label}
              </Pill>
            ))}
          </div>
        </div>

        <div className="mt-6 space-y-2">
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Modes</div>
          <div className="flex gap-2">
            <Toggle
              checked={props.onboardingMode}
              onChange={props.setOnboardingMode}
              label="Onboarding mode"
              hint="Write for new contributors"
            />
            <Toggle
              checked={props.selfCritique}
              onChange={props.setSelfCritique}
              label="Self-critique pass"
              hint="+8s · higher quality"
            />
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-border bg-card px-4 py-3">
        <button
          onClick={props.onGenerate}
          disabled={!props.sourceCode || generating || props.formats.length === 0}
          className={cn(
            "inline-flex h-10 w-full items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors duration-150",
            generating
              ? "cursor-wait bg-brand/80 text-primary-foreground"
              : "bg-brand text-primary-foreground hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          {generating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating…
            </>
          ) : props.status === "done" ? (
            <>↻ Regenerate</>
          ) : props.status === "error" ? (
            <>⚠ Retry</>
          ) : (
            <>▶ Generate docs</>
          )}
        </button>
      </div>
    </section>
  );
}
