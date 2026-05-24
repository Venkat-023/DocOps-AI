import { useCallback, useEffect, useRef, useState } from "react";

export type DocStatus = "idle" | "fetching" | "generating" | "done" | "error";

type SymbolKind = "function" | "class" | "method";

interface BackendSymbol {
  name: string;
  type: SymbolKind;
  line_start: number;
  line_end: number;
  params: string[];
  return_type?: string | null;
  is_async: boolean;
  docstring?: string | null;
}

interface ParsedSymbols {
  functions: BackendSymbol[];
  classes: BackendSymbol[];
  line_count: number;
  language: string;
  imports: string[];
}

export interface Symbols {
  functions: number;
  classes: number;
  lineCount: number;
  language: string;
  raw?: ParsedSymbols;
}

interface GenerateOpts {
  formats: string[];
  onboardingMode: boolean;
  selfCritique: boolean;
}

interface FetchGithubResponse {
  content: string;
  file_path: string;
  language: string;
  is_pr: boolean;
  symbols: ParsedSymbols;
}

const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

function toDisplaySymbols(symbols: ParsedSymbols): Symbols {
  return {
    functions: symbols.functions.length,
    classes: symbols.classes.length,
    lineCount: symbols.line_count,
    language: symbols.language,
    raw: symbols,
  };
}

function inferLanguage(label: string, code: string) {
  const lower = label.toLowerCase();
  if (lower.endsWith(".py") || /\bdef\s+\w+/.test(code)) return "python";
  if (lower.endsWith(".ts") || lower.endsWith(".tsx") || /\binterface\s+\w+/.test(code)) return "typescript";
  if (lower.endsWith(".js") || lower.endsWith(".jsx")) return "javascript";
  if (lower.endsWith(".go")) return "go";
  if (lower.endsWith(".rs")) return "rust";
  if (lower.endsWith(".java")) return "java";
  if (lower.endsWith(".yaml") || lower.endsWith(".yml")) return "yaml";
  if (lower.endsWith(".json")) return "json";
  return "javascript";
}

function localSymbols(code: string, label: string): Symbols {
  const functions = (code.match(/\b(function|def|fn)\s+\w+|=>\s*{/g) ?? []).length;
  const classes = (code.match(/\bclass\s+\w+/g) ?? []).length;
  return {
    functions: Math.max(functions, 1),
    classes,
    lineCount: code.split("\n").length,
    language: inferLanguage(label, code),
  };
}

async function readError(response: Response) {
  try {
    const payload = await response.json();
    return payload.detail || "Request failed. Please try again.";
  } catch {
    return "Request failed. Please try again.";
  }
}

export function useDocGen() {
  const [status, setStatus] = useState<DocStatus>("idle");
  const [sourceCode, setSourceCode] = useState("");
  const [sourceLabel, setSourceLabel] = useState<string>("");
  const [symbols, setSymbols] = useState<Symbols | null>(null);
  const [output, setOutput] = useState("");
  const [quality, setQuality] = useState<null | {
    coverage: number;
    examples: number;
    params: number;
    edge_cases: number;
    overall?: number;
    improvements?: string[];
  }>(null);
  const [error, setError] = useState<string | null>(null);
  const [tokens, setTokens] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const fetchFromGitHub = useCallback(async (url: string) => {
    setStatus("fetching");
    setError(null);
    setOutput("");
    setQuality(null);

    try {
      const response = await fetch(`${API_URL}/fetch-github`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error(await readError(response));
      }

      const payload = (await response.json()) as FetchGithubResponse;
      setSourceCode(payload.content);
      setSourceLabel(payload.file_path);
      setSymbols(toDisplaySymbols(payload.symbols));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach backend. Is it running on port 8000?");
      setStatus("error");
    }
  }, []);

  const loadPasted = useCallback((code: string, label = "pasted snippet") => {
    setSourceCode(code);
    setSourceLabel(label);
    setSymbols(localSymbols(code, label));
    setStatus("idle");
    setOutput("");
    setQuality(null);
    setError(null);
  }, []);

  const generate = useCallback(
    async (opts: GenerateOpts) => {
      if (!sourceCode) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setStatus("generating");
      setOutput("");
      setQuality(null);
      setTokens(0);
      setError(null);

      try {
        const response = await fetch(`${API_URL}/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            code: sourceCode,
            symbols: symbols?.raw,
            format: opts.formats[0] ?? "readme",
            onboarding_mode: opts.onboardingMode,
            self_critique: opts.selfCritique,
            language: symbols?.language,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(await readError(response));
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            if (!frame.startsWith("data: ")) continue;

            const data = frame.slice(6);
            if (data === "[DONE]") {
              setStatus("done");
              return;
            }
            if (data.startsWith("[TOKENS]")) {
              setTokens(Number(data.replace("[TOKENS]", "")) || 0);
              continue;
            }
            if (data.startsWith("[SCORE]")) {
              setQuality(JSON.parse(data.replace("[SCORE]", "")));
              continue;
            }
            if (data.startsWith("[ERROR]")) {
              throw new Error(data.replace("[ERROR]", ""));
            }

            setOutput((previous) => previous + data.replace(/\\n/g, "\n"));
            setTokens((previous) => previous + 1);
          }
        }

        setStatus("done");
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Generation failed. Please try again.");
        setStatus("error");
      }
    },
    [sourceCode, symbols],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
    setOutput("");
    setSourceCode("");
    setSourceLabel("");
    setSymbols(null);
    setQuality(null);
    setError(null);
    setTokens(0);
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  return {
    status,
    sourceCode,
    sourceLabel,
    symbols,
    output,
    quality,
    error,
    tokens,
    fetchFromGitHub,
    loadPasted,
    generate,
    reset,
  };
}
