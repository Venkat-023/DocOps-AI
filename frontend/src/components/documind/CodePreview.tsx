import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

const langMap: Record<string, string> = {
  TypeScript: "typescript",
  JavaScript: "javascript",
  Python: "python",
  Go: "go",
  typescript: "typescript",
  javascript: "javascript",
  python: "python",
  go: "go",
};

export function CodePreview({ code, language }: { code: string; language: string }) {
  return (
    <div className="max-h-[280px] overflow-auto rounded-lg border border-border bg-card">
      <SyntaxHighlighter
        language={langMap[language] ?? "typescript"}
        style={oneLight}
        showLineNumbers
        customStyle={{
          margin: 0,
          background: "transparent",
          fontSize: 11,
          lineHeight: 1.55,
          padding: 12,
        }}
        lineNumberStyle={{ color: "var(--muted-foreground)", opacity: 0.5, minWidth: "2em" }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
