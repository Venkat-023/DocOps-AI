import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Download, ExternalLink, Check, GitPullRequest } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DocStatus } from "@/hooks/useDocGen";
import { FORMAT_OPTIONS, type FormatId } from "@/lib/constants";

type OutTab = "preview" | "raw" | "diff" | "score";

export function OutputPanel(props: {
  status: DocStatus;
  output: string;
  quality: null | { coverage: number; examples: number; params: number; edge_cases: number };
  sourceCode: string;
  formats: FormatId[];
}) {
  const [tab, setTab] = useState<OutTab>("preview");
  const [copied, setCopied] = useState(false);
  const generating = props.status === "generating";

  const onCopy = async () => {
    await navigator.clipboard.writeText(props.output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const onDownload = () => {
    const fmt = FORMAT_OPTIONS.find((f) => f.id === props.formats[0]) ?? FORMAT_OPTIONS[0];
    const blob = new Blob([props.output], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `documind${fmt.ext}`;
    a.click();
  };

  const tabs: { id: OutTab; label: string; disabled?: boolean }[] = [
    { id: "preview", label: "Preview" },
    { id: "raw", label: "Raw" },
    { id: "diff", label: "Diff view" },
    { id: "score", label: "Score", disabled: !props.quality },
  ];

  return (
    <section className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => !t.disabled && setTab(t.id)}
              disabled={t.disabled}
              className={cn(
                "rounded-pill border px-3 py-1 text-xs font-medium transition-colors duration-150",
                tab === t.id
                  ? "border-brand-border bg-brand-light text-brand-dark"
                  : "border-transparent text-muted-foreground hover:text-foreground",
                t.disabled && "cursor-not-allowed opacity-40 hover:text-muted-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={onCopy}
            disabled={!props.output}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-xs text-foreground transition-colors duration-150 hover:bg-accent disabled:opacity-50"
          >
            {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied!" : "Copy"}
          </button>
          <button
            onClick={onDownload}
            disabled={!props.output}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-xs text-foreground transition-colors duration-150 hover:bg-accent disabled:opacity-50"
          >
            <Download className="h-3 w-3" />
            Download
          </button>
          <button
            disabled={!props.output}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-xs text-foreground transition-colors duration-150 hover:bg-accent disabled:opacity-50"
          >
            <GitPullRequest className="h-3 w-3" />
            Open PR
            <ExternalLink className="h-2.5 w-2.5 opacity-60" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {!props.output && props.status !== "generating" ? (
          <EmptyState />
        ) : tab === "preview" ? (
          <MarkdownPreview output={props.output} generating={generating} />
        ) : tab === "raw" ? (
          <RawView output={props.output} />
        ) : tab === "diff" ? (
          <DiffViewer original={props.sourceCode} generated={props.output} />
        ) : (
          <ScoreDashboard quality={props.quality} />
        )}
      </div>
    </section>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <div className="rounded-2xl border border-dashed border-border px-8 py-10">
        <div className="text-sm font-medium text-foreground">No output yet</div>
        <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-muted-foreground">
          Fetch a file from GitHub or paste a snippet, pick a format, then press Generate. Output streams here in real time.
        </p>
      </div>
    </div>
  );
}

function MarkdownPreview({ output, generating }: { output: string; generating: boolean }) {
  // Smooth 60fps rendering: buffer external output into a displayed string.
  const bufferRef = useRef("");
  const lastRef = useRef("");
  const [display, setDisplay] = useState("");

  useEffect(() => {
    // accumulate diff into buffer
    if (output.length > lastRef.current.length && output.startsWith(lastRef.current)) {
      bufferRef.current += output.slice(lastRef.current.length);
    } else {
      // reset case
      bufferRef.current = "";
      setDisplay(output);
    }
    lastRef.current = output;
  }, [output]);

  useEffect(() => {
    const id = setInterval(() => {
      if (bufferRef.current.length > 0) {
        const chunk = bufferRef.current;
        bufferRef.current = "";
        setDisplay((p) => p + chunk);
      }
    }, 16);
    return () => clearInterval(id);
  }, []);

  return (
    <article className="prose prose-sm prose-neutral max-w-none px-8 py-6 prose-headings:font-semibold prose-headings:tracking-tight prose-pre:rounded-md prose-pre:border prose-pre:border-border prose-pre:bg-card prose-code:font-mono prose-code:text-[12px] prose-pre:p-0">
      <ReactMarkdown
        components={{
          code({ className, children, ...rest }) {
            const lang = /language-(\w+)/.exec(className ?? "")?.[1];
            const text = String(children).replace(/\n$/, "");
            const inline = !lang && !text.includes("\n");
            if (inline) {
              return (
                <code className="rounded bg-muted px-1 py-0.5 text-foreground" {...rest}>
                  {children}
                </code>
              );
            }
            return (
              <SyntaxHighlighter
                language={lang ?? "text"}
                style={oneLight}
                customStyle={{ margin: 0, padding: 14, background: "transparent", fontSize: 12 }}
              >
                {text}
              </SyntaxHighlighter>
            );
          },
        }}
      >
        {display}
      </ReactMarkdown>
      {generating && <span className="streaming-cursor" />}
    </article>
  );
}

function RawView({ output }: { output: string }) {
  return (
    <pre className="h-full overflow-auto whitespace-pre-wrap break-words px-8 py-6 font-mono text-xs leading-relaxed text-foreground">
      {output}
    </pre>
  );
}

function DiffViewer({ original, generated }: { original: string; generated: string }) {
  const genLines = useMemo(() => generated.split("\n"), [generated]);
  const origLines = useMemo(() => original.split("\n"), [original]);
  return (
    <div className="grid h-full grid-cols-2 gap-0 divide-x divide-border font-mono text-[11px] leading-relaxed">
      <div className="overflow-auto bg-card/40 px-4 py-4">
        <div className="mb-2 text-[10px] uppercase tracking-wider text-muted-foreground">Source</div>
        {origLines.map((l, i) => (
          <div key={i} className="flex gap-3 text-muted-foreground">
            <span className="w-6 select-none text-right opacity-40">{i + 1}</span>
            <span className="whitespace-pre">{l || " "}</span>
          </div>
        ))}
      </div>
      <div className="overflow-auto px-4 py-4">
        <div className="mb-2 text-[10px] uppercase tracking-wider text-muted-foreground">Generated</div>
        {genLines.map((l, i) => (
          <div key={i} className="flex gap-3">
            <span className="w-4 select-none text-success/70">+</span>
            <span className="whitespace-pre text-success">{l || " "}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreDashboard({ quality }: { quality: { coverage: number; examples: number; params: number; edge_cases: number } | null }) {
  if (!quality) return null;
  const metrics = [
    { label: "Coverage", value: quality.coverage, color: "var(--success)" },
    { label: "Examples", value: quality.examples, color: "var(--success)" },
    { label: "Param descriptions", value: quality.params, color: "var(--info)" },
    { label: "Edge cases", value: quality.edge_cases, color: "var(--warning)" },
  ];
  const overall = Math.round(metrics.reduce((s, m) => s + m.value, 0) / metrics.length);
  return (
    <div className="space-y-3 px-8 py-6">
      <div className="grid grid-cols-2 gap-3">
        {metrics.map((m) => (
          <div key={m.label} className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
            <Ring value={m.value} color={m.color} />
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{m.label}</div>
              <div className="mt-0.5 text-2xl font-medium tabular-nums text-foreground">{m.value}%</div>
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Overall score</div>
            <div className="mt-0.5 text-3xl font-medium tabular-nums text-foreground">{overall}%</div>
          </div>
          <div className="text-xs text-muted-foreground">Weighted across all metrics</div>
        </div>
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${overall}%` }} />
        </div>
      </div>
    </div>
  );
}

function Ring({ value, color }: { value: number; color: string }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return (
    <svg width="56" height="56" viewBox="0 0 56 56" className="-rotate-90">
      <circle cx="28" cy="28" r={r} stroke="var(--muted)" strokeWidth="4" fill="none" />
      <circle
        cx="28"
        cy="28"
        r={r}
        stroke={color}
        strokeWidth="4"
        fill="none"
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 600ms ease" }}
      />
    </svg>
  );
}
