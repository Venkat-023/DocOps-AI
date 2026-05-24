from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import httpx
from pathlib import Path

from api.config import settings
from api.routers import generate, github, health

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

FRONTEND_ASSETS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "client" / "assets"

DOCUMIND_FALLBACK_SCRIPT = r"""
<script>
(() => {
  if (window.__DOCUMIND_FALLBACK_BOUND) return;
  window.__DOCUMIND_FALLBACK_BOUND = true;

  const state = { sourceCode: "", sourceLabel: "", symbols: null, language: "markdown", format: "readme" };
  const byButtonText = (text) => [...document.querySelectorAll("button")]
    .find((button) => button.textContent.trim().includes(text));

  function ensurePanel(id, title) {
    let panel = document.getElementById(id);
    if (panel) return panel;
    const sections = document.querySelectorAll("section");
    const host = id === "documind-source-panel" ? sections[0] : sections[1] || document.body;
    panel = document.createElement("div");
    panel.id = id;
    panel.style.cssText = "margin:16px;padding:14px;border:1px solid #e5e5e5;border-radius:8px;background:#fff;font:12px Inter,system-ui,sans-serif;white-space:pre-wrap;max-height:320px;overflow:auto;";
    panel.innerHTML = `<strong>${title}</strong><div style="margin-top:8px;color:#737373">Waiting...</div>`;
    host.appendChild(panel);
    return panel;
  }

  function setPanel(id, title, html) {
    const panel = ensurePanel(id, title);
    panel.innerHTML = `<strong>${title}</strong><div style="margin-top:8px">${html}</div>`;
  }

  function setGenerateEnabled(enabled) {
    const button = byButtonText("Generate docs");
    if (button) {
      button.disabled = !enabled;
      button.style.opacity = enabled ? "1" : "";
      button.style.cursor = enabled ? "pointer" : "";
    }
  }

  async function fetchGithub() {
    const input = document.querySelector('input[type="url"]');
    const url = input && input.value.trim();
    if (!url) return;
    setPanel("documind-source-panel", "Source", "Fetching from GitHub...");
    try {
      const response = await fetch("/fetch-github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "GitHub fetch failed");
      state.sourceCode = payload.content;
      state.sourceLabel = payload.file_path;
      state.symbols = payload.symbols;
      state.language = payload.language;
      const lineCount = payload.symbols && payload.symbols.line_count ? payload.symbols.line_count : payload.content.split("\n").length;
      const functions = payload.symbols && payload.symbols.functions ? payload.symbols.functions.length : 0;
      const classes = payload.symbols && payload.symbols.classes ? payload.symbols.classes.length : 0;
      setPanel(
        "documind-source-panel",
        "Source loaded",
        `<code>${payload.file_path}</code><br>${lineCount} lines · ${functions} functions · ${classes} classes<br><br><pre style="margin:0;white-space:pre-wrap">${payload.content.slice(0, 2500).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</pre>`
      );
      setGenerateEnabled(true);
    } catch (error) {
      setPanel("documind-source-panel", "Fetch error", `<span style="color:#b91c1c">${error.message}</span>`);
    }
  }

  async function generateDocs() {
    if (!state.sourceCode) return;
    const button = byButtonText("Generate docs") || byButtonText("Regenerate");
    if (button) button.textContent = "Generating...";
    setPanel("documind-output-panel", "Generated documentation", "");
    const output = document.querySelector("#documind-output-panel div");
    try {
      const response = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: state.sourceCode,
          symbols: state.symbols,
          format: state.format,
          onboarding_mode: true,
          self_critique: true,
          language: state.language,
        }),
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
          if (data.startsWith("[TOKENS]") || data.startsWith("[SCORE]")) continue;
          output.textContent += data.replaceAll("\\n", "\n");
        }
      }
    } catch (error) {
      output.innerHTML = `<span style="color:#b91c1c">${error.message}</span>`;
    } finally {
      if (button) button.textContent = "↻ Regenerate";
    }
  }

  function bind() {
    byButtonText("Fetch")?.addEventListener("click", fetchGithub);
    byButtonText("Generate docs")?.addEventListener("click", generateDocs);
    ["README.md", "JSDoc", "OpenAPI YAML", "Confluence", "Docusaurus MDX"].forEach((label) => {
      byButtonText(label)?.addEventListener("click", () => {
        state.format = { "README.md": "readme", "JSDoc": "jsdoc", "OpenAPI YAML": "openapi", "Confluence": "confluence", "Docusaurus MDX": "docusaurus" }[label];
      });
    });
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
