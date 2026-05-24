import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { TopBar } from "@/components/documind/TopBar";
import { StatusBar } from "@/components/documind/StatusBar";
import { InputPanel } from "@/components/documind/InputPanel";
import { OutputPanel } from "@/components/documind/OutputPanel";
import { useDocGen } from "@/hooks/useDocGen";
import type { FormatId } from "@/lib/constants";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "DocuMind — AI documentation generator" },
      {
        name: "description",
        content:
          "Stream README, OpenAPI, JSDoc and more from any GitHub file. A premium developer tool for instant documentation.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const doc = useDocGen();
  const [formats, setFormats] = useState<FormatId[]>(["readme"]);
  const [onboardingMode, setOnboardingMode] = useState(true);
  const [selfCritique, setSelfCritique] = useState(false);

  return (
    <div className="flex h-screen min-h-0 flex-col bg-background text-foreground">
      <TopBar />
      <main className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(360px,440px)_1fr]">
        <InputPanel
          status={doc.status}
          sourceCode={doc.sourceCode}
          sourceLabel={doc.sourceLabel}
          symbols={doc.symbols}
          error={doc.error}
          formats={formats}
          setFormats={setFormats}
          onboardingMode={onboardingMode}
          setOnboardingMode={setOnboardingMode}
          selfCritique={selfCritique}
          setSelfCritique={setSelfCritique}
          onFetchGitHub={doc.fetchFromGitHub}
          onLoadPasted={doc.loadPasted}
          onGenerate={() => doc.generate({ formats, onboardingMode, selfCritique })}
        />
        <OutputPanel
          status={doc.status}
          output={doc.output}
          quality={doc.quality}
          sourceCode={doc.sourceCode}
          formats={formats}
        />
      </main>
      <StatusBar status={doc.status} tokens={doc.tokens} fileInfo={doc.sourceLabel || undefined} />
    </div>
  );
}
