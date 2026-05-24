---
title: DocuMind Ai
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# DocuMind AI

DocuMind AI is an AI-powered documentation generator for software projects. It fetches source code from GitHub or accepts pasted/uploaded code, extracts code structure, builds documentation-specific prompts, and streams generated documentation back to the user in real time.

The deployed Hugging Face Space is available at:

https://venkat-023-documind-ai.hf.space/

## Problem

Engineering teams often delay documentation because writing it manually is slow, repetitive, and hard to keep aligned with changing code. This creates several practical problems:

- New developers need more time to understand unfamiliar repositories.
- APIs and modules are used incorrectly because behavior, parameters, and edge cases are not documented.
- Pull requests ship code without matching README, JSDoc, OpenAPI, wiki, or Docusaurus updates.
- Documentation quality varies heavily between contributors.
- Frontend applications cannot reliably consume AI output unless the backend returns predictable, structured data.

DocuMind AI is built to reduce that friction by turning real source code into useful documentation quickly, while keeping the user in control of format, tone, and source input.

## Solution

DocuMind AI combines a TanStack React frontend with a FastAPI backend.

The backend handles four jobs:

1. Fetch code from GitHub.
2. Parse source code structure using AST extraction.
3. Build format-specific prompts for documentation generation.
4. Stream OpenAI output token by token to the frontend.

The frontend provides a developer-friendly interface for choosing input sources, output formats, onboarding mode, and self-critique scoring.

## Key Features

- Fetch code from GitHub file, repository, or pull request URLs.
- Paste or upload code directly from the UI.
- Extract functions, classes, methods, imports, line counts, parameters, async status, return types, and docstrings where available.
- Generate documentation in multiple formats:
  - README.md
  - JSDoc/docstrings
  - OpenAPI YAML
  - Confluence HTML
  - Docusaurus MDX
- Stream generated documentation live using Server-Sent Events.
- Optional self-critique pass that returns quality scores.
- Dockerized for Hugging Face Spaces.
- Same-origin deployment on Hugging Face to avoid CORS issues.

## Architecture

```text
User
  |
  v
TanStack React Frontend
  |
  | POST /fetch-github
  | POST /generate
  v
FastAPI Backend
  |
  |-- GitHub Service: fetches files, repo overview, or PR diff
  |-- Parser Service: extracts symbols using tree-sitter or regex fallback
  |-- Prompt Service: builds documentation prompts
  |-- OpenAI Service: streams generated text
  |-- Quality Service: scores documentation when enabled
  |
  v
OpenAI API
```

## Repository Structure

```text
.
├── api/
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── routers/
│   ├── services/
│   └── utils/
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Inputs

DocuMind AI supports these input types.

### 1. GitHub URL

Use a public GitHub URL or a private URL if `GITHUB_TOKEN` is configured.

Supported examples:

```text
https://github.com/owner/repo/blob/main/path/to/file.py
https://github.com/owner/repo/pull/123
https://github.com/owner/repo
```

Request shape:

```json
{
  "url": "https://github.com/owner/repo/blob/main/path/to/file.py"
}
```

### 2. Pasted Code

The user can paste source code directly into the frontend. The frontend infers a basic language and sends the code to the backend for generation.

### 3. Uploaded File

The user can upload source files such as:

```text
.ts, .tsx, .js, .jsx, .py, .go, .rs, .java
```

### 4. OpenAPI Spec

The user can paste an OpenAPI YAML or JSON specification and generate documentation around it.

## Outputs

### GitHub Fetch Output

Endpoint:

```text
POST /fetch-github
```

Response:

```json
{
  "content": "source code or diff text",
  "file_path": "path/to/file.py",
  "language": "python",
  "is_pr": false,
  "symbols": {
    "functions": [],
    "classes": [],
    "line_count": 120,
    "language": "python",
    "imports": []
  }
}
```

### Documentation Generation Output

Endpoint:

```text
POST /generate
```

The response is an SSE stream.

Stream frames:

```text
data: TOKEN
data: [TOKENS]42
data: [SCORE]{"coverage":90,"examples":85,"params":88,"edge_cases":75,"overall":85,"improvements":[]}
data: [DONE]
```

### Generated Documentation Formats

The generated output can be:

- Markdown README
- Inline JSDoc/docstrings
- OpenAPI 3.1 YAML
- Confluence HTML
- Docusaurus MDX

## API Contract

### `GET /health`

Returns backend status.

```json
{
  "status": "ok",
  "model": "openrouter/free or local-fallback",
  "llm_provider": "openrouter",
  "github_configured": true
}
```

### `POST /fetch-github`

Fetches code from GitHub and returns parsed symbols.

Request:

```json
{
  "url": "https://github.com/owner/repo/blob/main/file.py"
}
```

### `POST /generate`

Streams documentation.

Request:

```json
{
  "code": "def hello():\n    return 'world'",
  "symbols": null,
  "format": "readme",
  "onboarding_mode": true,
  "self_critique": true,
  "language": "python"
}
```

Valid `format` values:

```text
readme
jsdoc
openapi
confluence
docusaurus
```

## Error Handling

The backend returns structured `detail` messages so the frontend can display clear user-facing errors.

Common errors:

```json
{ "detail": "Cannot parse GitHub URL. Paste a direct file URL like github.com/owner/repo/blob/main/file.py" }
```

```json
{ "detail": "OpenAI API key not configured" }
```

```json
{ "detail": "File too large (1200 lines). Maximum is 800 lines." }
```

```json
{ "detail": "Rate limit hit. Wait 30 seconds and retry." }
```

```json
{ "detail": "Could not reach GitHub. Check the URL and try again." }
```

## Environment Variables

Backend:

```text
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
GITHUB_TOKEN=ghp_...
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LLM_PROVIDER=auto
OPENAI_MODEL=gpt-4.1-mini
OPENROUTER_MODEL=openrouter/free
MAX_FILE_SIZE_LINES=800
MAX_OUTPUT_TOKENS=4000
```

Frontend:

```text
VITE_API_URL=http://localhost:8000
```

On Hugging Face, the frontend uses same-origin routes through the Vite proxy, so `VITE_API_URL` can be omitted.

## Local Development

### 1. Install Backend Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Backend

Create `.env` in the repository root:

```text
OPENAI_API_KEY=your_openai_key
GITHUB_TOKEN=your_github_token_optional
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 3. Start Backend

```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 5. Configure Frontend

Create `frontend/.env.local`:

```text
VITE_API_URL=http://localhost:8000
```

### 6. Start Frontend

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

Open:

```text
http://localhost:5173
```

## Docker Deployment

The Dockerfile is designed for Hugging Face Spaces.

It does the following:

1. Starts from `python:3.11-slim`.
2. Installs Node.js.
3. Installs Python backend dependencies.
4. Copies the FastAPI backend and TanStack frontend.
5. Installs frontend dependencies.
6. Starts FastAPI on internal port `8000`.
7. Starts Vite on exposed port `7860`.
8. Proxies frontend API calls to FastAPI.

Hugging Face uses:

```text
sdk: docker
app_port: 7860
```

## Hugging Face Deployment

Space:

```text
https://huggingface.co/spaces/Venkat-023/DocuMind-Ai
```

Optional free-model Space secret:

```text
OPENROUTER_API_KEY
```

Other optional Space secrets:

```text
OPENAI_API_KEY
GITHUB_TOKEN
```

After setting secrets, restart the Space from the Hugging Face settings page.

## How To Use

1. Open the app.
2. Choose an input method:
   - GitHub URL
   - Upload file
   - Paste code
   - OpenAPI spec
3. Load the source.
4. Select one or more documentation formats.
5. Choose modes:
   - Onboarding mode for beginner-friendly documentation.
   - Self-critique pass for quality scoring.
6. Click **Generate docs**.
7. Watch the documentation stream into the output panel.
8. Copy or download the result.

## Structured Implementation Plan

### Phase 1: Backend Foundation

- Create FastAPI app.
- Add CORS configuration.
- Add `/health`, `/fetch-github`, and `/generate`.
- Define Pydantic request and response models.
- Add environment-based settings.

### Phase 2: GitHub Fetching

- Parse GitHub file, repo, and PR URLs.
- Fetch single files using PyGithub.
- Fetch PR file patches.
- Fetch repository README and top-level tree for overview mode.
- Return predictable structured payloads.

### Phase 3: Code Understanding

- Detect language from file extension.
- Parse supported languages with tree-sitter.
- Extract symbols:
  - functions
  - classes
  - methods
  - parameters
  - line ranges
  - return types
  - docstrings
- Fall back to regex for unsupported languages.

### Phase 4: Prompt Engineering

- Create separate prompt templates for each output format.
- Add technical and onboarding tones.
- Inject symbol summaries into prompts.
- Limit prompt input size to keep requests reliable.

### Phase 5: Streaming Generation

- Use OpenAI Responses API.
- Stream tokens through FastAPI as SSE.
- Collect output for optional quality scoring.
- Send special frames for token counts, score, errors, and completion.

### Phase 6: Frontend Integration

- Replace mock generation with real backend calls.
- Parse SSE frames in the browser.
- Display streamed output in real time.
- Show structured errors from backend `detail`.
- Display symbol counts and quality scores.

### Phase 7: Deployment

- Dockerize frontend and backend together.
- Run frontend on Hugging Face port `7860`.
- Run backend internally on `8000`.
- Proxy API requests from frontend to backend.
- Store API keys as Hugging Face secrets.

## Current Limitations

- Tree-sitter extraction is strongest for Python and JavaScript.
- TypeScript currently uses JavaScript parser fallback behavior.
- Very large files are rejected based on `MAX_FILE_SIZE_LINES`.
- Generation requires a valid `OPENAI_API_KEY`.
- Private GitHub repositories require `GITHUB_TOKEN`.

## Security Notes

- Do not commit `.env` files.
- Do not paste long-lived API keys into source files.
- Use Hugging Face Space secrets for deployment credentials.
- Rotate any API key that has been exposed in chat, logs, screenshots, or commits.

## License

Add the project license here before public production release.
