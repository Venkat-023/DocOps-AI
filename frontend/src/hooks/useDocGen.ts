import { useCallback, useEffect, useRef, useState } from "react";

export type DocStatus = "idle" | "fetching" | "generating" | "done" | "error";

export interface Symbols {
  functions: number;
  classes: number;
  lineCount: number;
  language: string;
}

interface GenerateOpts {
  formats: string[];
  onboardingMode: boolean;
  selfCritique: boolean;
}

interface ApiSymbol {
  name: string;
  type: "function" | "class" | "method";
  line_start: number;
  line_end: number;
  params: string[];
  return_type?: string | null;
  is_async: boolean;
  docstring?: string | null;
}

interface ParsedSymbols {
  functions: ApiSymbol[];
  classes: ApiSymbol[];
  line_count: number;
  language: string;
  imports: string[];
}

interface FetchGitHubResponse {
  content: string;
  file_path: string;
  language: string;
  is_pr: boolean;
  symbols: ParsedSymbols;
}

const API_BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "";

function toUiSymbols(symbols: ParsedSymbols): Symbols {
  return {
    functions: symbols.functions.length,
    classes: symbols.classes.length,
    lineCount: symbols.line_count,
    language: symbols.language,
  };
}

function guessLanguage(label: string, code: string) {
  if (label.endsWith(".py") || /\bdef\s+\w+/.test(code)) return "python";
  if (label.endsWith(".go") || /\bfunc\s+\w+/.test(code)) return "go";
  if (label.endsWith(".ts") || label.endsWith(".tsx") || /\binterface\s+\w+/.test(code)) return "typescript";
  return "javascript";
}

function localSymbols(code: string, label = "pasted snippet"): Symbols {
  const functions = (code.match(/\b(function|def|fn|func)\s+\w+|=>\s*{/g) ?? []).length;
  const classes = (code.match(/\bclass\s+\w+/g) ?? []).length;
  return {
    functions: Math.max(functions, 1),
    classes,
    lineCount: code.split("\n").length,
    language: guessLanguage(label, code),
  };
}

async function readApiError(response: Response) {
  try {
    const body = await response.json();
    return body.detail || "Request failed. Try again.";
  } catch {
    return "Request failed. Try again.";
  }
}

export function useDocGen() {
  const [status, setStatus] = useState<DocStatus>("idle");
  const [sourceCode, setSourceCode] = useState("");
  const [sourceLabel, setSourceLabel] = useState<string>("");
  const [symbols, setSymbols] = useState<Symbols | null>(null);
  const [rawSymbols, setRawSymbols] = useState<ParsedSymbols | null>(null);
  const [output, setOutput] = useState("");
  const [quality, setQuality] = useState<null | {
    coverage: number;
    examples: number;
    params: number;
    edge_cases: number;
  }>(null);
  const [error, setError] = useState<string | null>(null);
  const [tokens, setTokens] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const fetchFromGitHub = useCallback(async (url: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("fetching");
    setError(null);
    setOutput("");
    setQuality(null);

    try {
      const response = await fetch(`${API_BASE}/fetch-github`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(await readApiError(response));

      const data = (await response.json()) as FetchGitHubResponse;
      setSourceCode(data.content);
      setSourceLabel(data.file_path);
      setSymbols(toUiSymbols(data.symbols));
      setRawSymbols(data.symbols);
      setStatus("idle");
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError((err as Error).message);
      setStatus("error");
    }
  }, []);

  const loadPasted = useCallback((code: string, label = "pasted snippet") => {
    setSourceCode(code);
    setSourceLabel(label);
    setSymbols(localSymbols(code, label));
    setRawSymbols(null);
    setStatus("idle");
    setError(null);
    setOutput("");
    setQuality(null);
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
        const response = await fetch(`${API_BASE}/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code: sourceCode,
            symbols: rawSymbols,
            format: opts.formats[0] ?? "readme",
            onboarding_mode: opts.onboardingMode,
            self_critique: opts.selfCritique,
            language: symbols?.language,
          }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) throw new Error(await readApiError(response));

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
            if (data.startsWith("[ERROR]")) {
              throw new Error(data.replace("[ERROR]", ""));
            }
            if (data.startsWith("[TOKENS]")) {
              setTokens(Number(data.replace("[TOKENS]", "")) || 0);
              continue;
            }
            if (data.startsWith("[SCORE]")) {
              const parsed = JSON.parse(data.replace("[SCORE]", ""));
              setQuality({
                coverage: parsed.coverage ?? 0,
                examples: parsed.examples ?? 0,
                params: parsed.params ?? 0,
                edge_cases: parsed.edge_cases ?? 0,
              });
              continue;
            }

            const token = data.replace(/\\n/g, "\n");
            setOutput((current) => current + token);
            setTokens((current) => current + 1);
          }
        }

        setStatus("done");
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError((err as Error).message);
        setStatus("error");
      }
    },
    [rawSymbols, sourceCode, symbols?.language],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
    setOutput("");
    setSourceCode("");
    setSourceLabel("");
    setSymbols(null);
    setRawSymbols(null);
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
