from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from api.config import settings
from api.routers import chat, generate, github, health

app = FastAPI(title="DocuMind AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(github.router, prefix="/fetch-github", tags=["github"])
app.include_router(generate.router, prefix="/generate", tags=["generate"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

FRONTEND_ASSETS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "client" / "assets"

DOCUMIND_FALLBACK_SCRIPT = r"""
<script>
(() => {
  if (window.__DOCUMIND_FALLBACK_BOUND) return;
  window.__DOCUMIND_FALLBACK_BOUND = true;

  const state = { sourceCode: "", sourceLabel: "", symbols: null, language: "markdown", format: "readme", output: "", score: null, onboarding: true, critique: true, chatHistory: [] };
  const formatMap = { "README.md": "readme", "JSDoc": "jsdoc", "OpenAPI YAML": "openapi", "Confluence": "confluence", "Docusaurus MDX": "docusaurus" };
  const extMap = { readme: ".md", jsdoc: ".js", openapi: ".yaml", confluence: ".html", docusaurus: ".mdx" };
  const byButtonText = (text) => [...document.querySelectorAll("button")].find((button) => button.textContent.trim().includes(text));
  const escapeHtml = (value) => String(value).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  function ensurePanel(id, title) {
    let panel = document.getElementById(id);
    if (panel) return panel;
    const sections = document.querySelectorAll("section");
    const host = id === "documind-source-panel" ? sections[0] : sections[1] || document.body;
    panel = document.createElement("div");
    panel.id = id;
    panel.style.cssText = "margin:16px;padding:14px;border:1px solid #e5e5e5;border-radius:8px;background:#fff;font:12px Inter,system-ui,sans-serif;white-space:pre-wrap;max-height:340px;overflow:auto;";
    panel.innerHTML = `<strong>${title}</strong><div style="margin-top:8px;color:#737373">Waiting...</div>`;
    host.appendChild(panel);
    return panel;
  }

  function setPanel(id, title, html) {
    const panel = ensurePanel(id, title);
    panel.innerHTML = `<strong>${title}</strong><div style="margin-top:8px">${html}</div>`;
  }

  function setGenerateEnabled(enabled) {
    const button = byButtonText("Generate docs") || byButtonText("Regenerate");
    if (button) {
      button.disabled = !enabled;
      button.style.opacity = enabled ? "1" : "";
      button.style.cursor = enabled ? "pointer" : "";
    }
  }

  function setActiveFormat(label) {
    Object.keys(formatMap).forEach((item) => {
      const button = byButtonText(item);
      if (button) button.style.outline = item === label ? "2px solid #a78bfa" : "";
    });
  }

  function fallbackSymbols(content, language) {
    return { functions: [], classes: [], line_count: content.split("\n").length, language, imports: [] };
  }

  function loadSource(content, label, language, symbols) {
    state.sourceCode = content;
    state.sourceLabel = label;
    state.language = language || "text";
    state.symbols = symbols || fallbackSymbols(content, state.language);
    state.output = "";
    state.score = null;
    state.chatHistory = [];
    const lineCount = state.symbols.line_count || content.split("\n").length;
    const functions = state.symbols.functions ? state.symbols.functions.length : 0;
    const classes = state.symbols.classes ? state.symbols.classes.length : 0;
    setPanel("documind-source-panel", "Source loaded", `<code>${escapeHtml(label)}</code><br>${lineCount} lines - ${functions} functions - ${classes} classes<br><br><pre style="margin:0;white-space:pre-wrap">${escapeHtml(content.slice(0, 3500))}</pre>`);
    setPanel("documind-output-panel", "Output", "No output yet. Press Generate docs.");
    ensureChatPanel();
    setGenerateEnabled(true);
  }

  function resetForNewUrl() {
    state.sourceCode = "";
    state.sourceLabel = "";
    state.symbols = null;
    state.output = "";
    state.score = null;
    state.chatHistory = [];
    setPanel("documind-source-panel", "GitHub URL", "Paste a repository, file, or pull request URL above, then press Fetch.");
    setPanel("documind-output-panel", "Output", "No output yet.");
    setGenerateEnabled(false);
  }

  function showPaste(label) {
    setPanel("documind-source-panel", label, `<textarea id="documind-paste-box" style="width:100%;min-height:180px;border:1px solid #d4d4d4;border-radius:6px;padding:10px;font:12px ui-monospace,monospace" placeholder="Paste code, README, or OpenAPI YAML here"></textarea><div style="margin-top:10px"><button id="documind-load-paste" type="button" style="border:1px solid #d4d4d4;border-radius:6px;padding:6px 10px;background:#fff">Load ${label}</button></div>`);
    document.getElementById("documind-load-paste")?.addEventListener("click", () => {
      const value = document.getElementById("documind-paste-box")?.value || "";
      if (!value.trim()) return;
      loadSource(value, label === "OpenAPI" ? "openapi.yaml" : "pasted snippet", label === "OpenAPI" ? "yaml" : "text", null);
    });
  }

  function showUpload() {
    setPanel("documind-source-panel", "Upload file", `<input id="documind-upload-file" type="file" style="display:block;margin-top:8px" /><p style="color:#737373;margin-top:8px">Choose a source file, notebook, README, or OpenAPI spec.</p>`);
    document.getElementById("documind-upload-file")?.addEventListener("change", async (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const text = await file.text();
      const language = file.name.endsWith(".py") ? "python" : file.name.endsWith(".ts") ? "typescript" : file.name.endsWith(".js") ? "javascript" : file.name.endsWith(".md") ? "markdown" : "text";
      loadSource(text, file.name, language, null);
    });
  }

  async function fetchGithub() {
    const input = document.querySelector('input[type="url"]');
    const url = input && input.value.trim();
    if (!url) return;
    setPanel("documind-source-panel", "Source", "Scanning GitHub repository and files...");
    try {
      const response = await fetch("/fetch-github", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "GitHub fetch failed");
      loadSource(payload.content, payload.file_path, payload.language, payload.symbols);
    } catch (error) {
      setPanel("documind-source-panel", "Fetch error", `<span style="color:#b91c1c">${escapeHtml(error.message)}</span>`);
    }
  }

  async function generateDocs() {
    if (!state.sourceCode) return;
    const button = byButtonText("Generate docs") || byButtonText("Regenerate");
    if (button) button.textContent = "Generating...";
    state.output = "";
    state.score = null;
    setPanel("documind-output-panel", "Generated documentation", "");
    const output = document.querySelector("#documind-output-panel div");
    try {
      const response = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: state.sourceCode, symbols: state.symbols, format: state.format, onboarding_mode: state.onboarding, self_critique: state.critique, language: state.language }),
      });
      if (!response.ok || !response.body) throw new Error("Generation failed");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (const frame of frames) {
          if (!frame.startsWith("data: ")) continue;
          const data = frame.slice(6);
          if (data === "[DONE]") break;
          if (data.startsWith("[ERROR]")) throw new Error(data.slice(7));
          if (data.startsWith("[TOKENS]")) continue;
          if (data.startsWith("[SCORE]")) {
            try { state.score = JSON.parse(data.slice(7)); } catch (_) {}
            continue;
          }
          const token = data.replaceAll("\\n", "\n");
          state.output += token;
          output.textContent += token;
        }
      }
    } catch (error) {
      output.innerHTML = `<span style="color:#b91c1c">${escapeHtml(error.message)}</span>`;
    } finally {
      if (button) button.textContent = "Regenerate";
    }
  }

  function showOutput(mode) {
    if (mode === "diff") {
      setPanel("documind-output-panel", "Diff view", `<strong>Source</strong><pre style="white-space:pre-wrap;max-height:150px;overflow:auto">${escapeHtml(state.sourceCode.slice(0, 1600) || "No source loaded.")}</pre><strong>Generated</strong><pre style="white-space:pre-wrap;max-height:180px;overflow:auto">${escapeHtml(state.output || "No output yet.")}</pre>`);
      return;
    }
    if (mode === "score") {
      const score = state.score || {};
      setPanel("documind-output-panel", "Score", `Coverage: ${score.coverage ?? "-"}%<br>Examples: ${score.examples ?? "-"}%<br>Params: ${score.params ?? "-"}%<br>Edge cases: ${score.edge_cases ?? "-"}%<br>Overall: ${score.overall ?? "-"}%`);
      return;
    }
    setPanel("documind-output-panel", mode === "raw" ? "Raw output" : "Preview", `<pre style="white-space:pre-wrap;margin:0">${escapeHtml(state.output || "No output yet.")}</pre>`);
  }

  async function copyOutput() {
    if (!state.output) return;
    try {
      await navigator.clipboard.writeText(state.output);
    } catch (_) {
      const textarea = document.createElement("textarea");
      textarea.value = state.output;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
  }

  function downloadOutput() {
    if (!state.output) return;
    const blob = new Blob([state.output], { type: "text/plain" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `documind${extMap[state.format] || ".md"}`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function ensureChatPanel() {
    let panel = document.getElementById("documind-chat-panel");
    if (panel) return panel;
    const sections = document.querySelectorAll("section");
    const host = sections[1] || document.body;
    panel = document.createElement("div");
    panel.id = "documind-chat-panel";
    panel.style.cssText = "margin:16px;padding:14px;border:1px solid #ddd6fe;border-radius:8px;background:#fafaff;font:12px Inter,system-ui,sans-serif;";
    panel.innerHTML = `
      <strong>Ask about this repo/report</strong>
      <div id="documind-chat-log" style="margin-top:8px;max-height:220px;overflow:auto;white-space:pre-wrap;color:#262626"></div>
      <div style="margin-top:10px;display:flex;gap:8px">
        <input id="documind-chat-input" style="flex:1;border:1px solid #d4d4d4;border-radius:6px;padding:8px" placeholder="Ask about files, model results, setup, risks..." />
        <button id="documind-chat-send" type="button" style="border:1px solid #7c3aed;border-radius:6px;padding:8px 12px;background:#7c3aed;color:white">Ask</button>
      </div>
    `;
    host.appendChild(panel);
    document.getElementById("documind-chat-send")?.addEventListener("click", askChat);
    document.getElementById("documind-chat-input")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") askChat();
    });
    return panel;
  }

  function appendChat(role, text) {
    ensureChatPanel();
    const log = document.getElementById("documind-chat-log");
    const label = role === "user" ? "You" : "DocuMind";
    log.textContent += `${label}: ${text}\n\n`;
    log.scrollTop = log.scrollHeight;
  }

  async function askChat() {
    const input = document.getElementById("documind-chat-input");
    const question = input?.value.trim();
    if (!question) return;
    input.value = "";
    appendChat("user", question);
    appendChat("assistant", "Thinking...");
    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          source: state.sourceCode,
          report: state.output,
          source_label: state.sourceLabel,
          history: state.chatHistory.slice(-8),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Chat failed");
      const log = document.getElementById("documind-chat-log");
      log.textContent = log.textContent.replace(/DocuMind: Thinking\.\.\.\n\n$/, "");
      appendChat("assistant", payload.answer);
      state.chatHistory.push({ role: "user", content: question }, { role: "assistant", content: payload.answer });
    } catch (error) {
      const log = document.getElementById("documind-chat-log");
      log.textContent = log.textContent.replace(/DocuMind: Thinking\.\.\.\n\n$/, "");
      appendChat("assistant", `Chat error: ${error.message}`);
    }
  }

  function bind() {
    ["Score", "Copy", "Download", "Open PR"].forEach((label) => {
      const button = byButtonText(label);
      if (button) {
        button.disabled = false;
        button.style.opacity = "1";
        button.style.cursor = "pointer";
      }
    });
    byButtonText("Fetch")?.addEventListener("click", fetchGithub);
    byButtonText("Generate docs")?.addEventListener("click", generateDocs);
    byButtonText("Docs")?.addEventListener("click", () => setPanel("documind-output-panel", "Docs", "Fetch a GitHub repo or load code, choose a format, then Generate docs."));
    byButtonText("Changelog")?.addEventListener("click", () => setPanel("documind-output-panel", "Changelog", "Latest deployed fix: repository scanning plus fallback controls for Hugging Face."));
    byButtonText("Sign in")?.addEventListener("click", () => setPanel("documind-output-panel", "Sign in", "Authentication is not required for this demo."));
    byButtonText("GitHub URL")?.addEventListener("click", resetForNewUrl);
    byButtonText("Upload")?.addEventListener("click", showUpload);
    byButtonText("Paste code")?.addEventListener("click", () => showPaste("Paste code"));
    byButtonText("OpenAPI")?.addEventListener("click", () => showPaste("OpenAPI"));
    byButtonText("Preview")?.addEventListener("click", () => showOutput("preview"));
    byButtonText("Raw")?.addEventListener("click", () => showOutput("raw"));
    byButtonText("Diff view")?.addEventListener("click", () => showOutput("diff"));
    byButtonText("Score")?.addEventListener("click", () => showOutput("score"));
    byButtonText("Copy")?.addEventListener("click", copyOutput);
    byButtonText("Download")?.addEventListener("click", downloadOutput);
    byButtonText("Open PR")?.addEventListener("click", () => setPanel("documind-output-panel", "Open PR", "PR creation is not connected in this demo. Use Copy or Download for the generated docs."));
    ensureChatPanel();
    document.querySelectorAll('button[role="switch"]').forEach((button, index) => {
      button.addEventListener("click", () => {
        if (index === 0) state.onboarding = !state.onboarding;
        if (index === 1) state.critique = !state.critique;
        button.style.outline = "2px solid #a78bfa";
      });
    });
    Object.keys(formatMap).forEach((label) => {
      byButtonText(label)?.addEventListener("click", () => {
        state.format = formatMap[label];
        setActiveFormat(label);
      });
    });
    setActiveFormat("README.md");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
</script>
"""


def _compiled_stylesheet() -> Path | None:
    stylesheets = sorted(FRONTEND_ASSETS_DIR.glob("styles-*.css"))
    return stylesheets[-1] if stylesheets else None


@app.get("/src/styles.css", include_in_schema=False)
@app.get("/@tanstack-start/styles.css", include_in_schema=False)
async def frontend_stylesheet():
    stylesheet = _compiled_stylesheet()
    if stylesheet:
        return FileResponse(
            stylesheet,
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream_response = await client.get("http://127.0.0.1:5173/src/styles.css")
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            media_type=upstream_response.headers.get("content-type"),
            headers={"Cache-Control": "no-store"},
        )


@app.api_route("/{path:path}", methods=["GET", "HEAD", "OPTIONS"])
async def frontend_proxy(path: str, request: Request):
    upstream = f"http://127.0.0.1:5173/{path}"
    if request.url.query:
        upstream = f"{upstream}?{request.url.query}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream_request = client.build_request(request.method, upstream)
        upstream_response = await client.send(upstream_request, stream=True)

        excluded_headers = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        }
        headers = {
            key: value
            for key, value in upstream_response.headers.items()
            if key.lower() not in excluded_headers
        }

        body = await upstream_response.aread()
        content_type = upstream_response.headers.get("content-type", "")
        if "text/html" in content_type:
            body = body.replace(b'/src/styles.css"', b'/src/styles.css?v=compiled"')
            body = body.replace(
                b'/@tanstack-start/styles.css?routes=',
                b'/@tanstack-start/styles.css?v=compiled&routes=',
            )
            body = body.replace(b"</body>", DOCUMIND_FALLBACK_SCRIPT.encode("utf-8") + b"</body>")
        return Response(
            content=body,
            status_code=upstream_response.status_code,
            headers=headers,
            media_type=content_type,
        )
