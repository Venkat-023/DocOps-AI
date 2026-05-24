---
title: DocuMind Ai
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# DocuMind AI

DocuMind AI is an AI-powered documentation and repository intelligence platform. It fetches code from GitHub, scans real repository files, extracts structure from source code, generates professional documentation, and lets users chat with the generated report and uploaded repository context.

Live deployment: https://venkat-023-documind-ai.hf.space/

Hugging Face Space: https://huggingface.co/spaces/Venkat-023/DocuMind-Ai

GitHub repository: https://github.com/Venkat-023/DocOps-AI

## The Problem

Most software teams do not have a documentation problem because they do not care. They have a documentation problem because useful documentation is expensive to keep current.

Common pain points:

- New contributors spend hours reading code before understanding the project.
- README files explain setup, but not the actual implementation.
- Generated docs often describe only one pasted file instead of the real repository.
- Code review and onboarding suffer when model results, API behavior, config, and file responsibilities are scattered across the repo.
- Users need follow-up answers after a report is generated, but normal documentation generators stop after one output.
- OpenAI credits or rate limits can block demos if the system has no fallback.

DocuMind AI solves this by combining repository scanning, documentation generation, and a fast RAG-style chatbot in one deployed app.

## Our MVP

The MVP is a working end-to-end documentation assistant for code repositories.

It can:

- Accept a GitHub repository, file, or pull request URL.
- Scan repository files, not only the README.
- Extract useful code and project structure.
- Generate a detailed report or documentation output.
- Stream generation results in the UI.
- Let users ask follow-up questions about the repo/report through a chatbot.
- Provide evidence when asked for proof, facts, files, or metrics.
- Run on Hugging Face Spaces using Docker.
- Work with OpenRouter, OpenAI, or a local fallback path when no paid LLM credits are available.

The most important MVP outcome is simple: a user can paste a GitHub repo URL, generate documentation, then ask "Which file trains this model?" or "What proof do you have?" and receive a grounded answer with citations from the scanned context.

## Key Features

### Repository Intelligence

- Supports whole GitHub repositories.
- Supports single GitHub files using `/blob/`.
- Supports pull request URLs using `/pull/`.
- Fetches README plus representative source/config files.
- Scans real implementation files such as training scripts, services, config files, and report files.
- Returns structured data the frontend can use without guessing.

### Code Understanding

- Detects language from file extensions.
- Extracts symbols from source code:
  - functions
  - classes
  - methods
  - parameters
  - line counts
  - imports
  - async status
  - docstrings where available
- Uses tree-sitter where supported.
- Uses regex fallback for unsupported languages.

### Documentation Generation

Supported output formats:

- `README.md`
- JSDoc/docstrings
- OpenAPI YAML
- Confluence HTML
- Docusaurus MDX

Generation modes:

- Technical mode for experienced developers.
- Onboarding mode for new contributors.
- Optional self-critique scoring.
- Streaming output through Server-Sent Events.

### RAG Chatbot

DocuMind includes a chatbot for follow-up questions about the generated report, uploaded documents, or scanned GitHub repository.

The chatbot can answer questions like:

- "Explain this project to a new user."
- "Which file trains the BiGRU model?"
- "What proof do you have?"
- "What are the dataset facts from the README?"
- "Which files should I inspect first?"
- "What are the model result metrics?"

When asked for proof or facts, it points to the relevant evidence from the loaded context, such as:

- scanned file names
- README sections
- code snippets
- table rows
- model metrics
- command examples
- class/function names

The chatbot uses:

- OpenRouter when `OPENROUTER_API_KEY` is configured.
- OpenAI when `OPENAI_API_KEY` and `LLM_PROVIDER=openai` are configured.
- A fast local retrieval fallback when no paid LLM key is available.

### Frontend Experience

- GitHub URL input.
- Upload flow.
- Paste code flow.
- OpenAPI input flow.
- Output format selection.
- Preview, raw, diff, and score tabs.
- Copy and download actions.
- Chat panel for repo/report questions.
- Same-origin Hugging Face deployment to avoid CORS failures.

## Architecture

```text
User
  |
  v
React / TanStack Frontend
  |
  | POST /fetch-github
  | POST /generate
  | POST /chat
  v
FastAPI Backend
  |
  |-- GitHub Service
  |     Fetches repo README, source files, single files, or PR diffs
  |
  |-- Parser Service
  |     Extracts AST/code symbols and fallback metadata
  |
  |-- Prompt Service
  |     Builds format-specific documentation prompts
  |
  |-- OpenAI/OpenRouter Service
  |     Streams generated documentation or uses local fallback
  |
  |-- Chat Service
  |     Ranks source/report chunks and answers with evidence
  |
  v
LLM Provider or Local Fallback
```

## Repository Structure

```text
.
|-- api/
|   |-- main.py
|   |-- config.py
|   |-- models/
|   |   |-- request_models.py
|   |   `-- response_models.py
|   |-- routers/
|   |   |-- health.py
|   |   |-- github.py
|   |   |-- generate.py
|   |   `-- chat.py
|   |-- services/
|   |   |-- github_service.py
|   |   |-- parser_service.py
|   |   |-- prompt_service.py
|   |   |-- openai_service.py
|   |   |-- quality_service.py
|   |   `-- chat_service.py
|   `-- utils/
|       |-- language_detect.py
|       `-- code_chunker.py
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- vite.config.ts
|-- Dockerfile
|-- backend.Dockerfile
|-- frontend.Dockerfile
|-- docker-compose.yml
|-- start.sh
|-- requirements.txt
`-- README.md
```

## API Contract

### `GET /health`

Checks whether the backend is running and which provider configuration is active.

Example response:

```json
{
  "status": "ok",
  "model": "openrouter/free",
  "llm_provider": "auto",
  "github_configured": true
}
```

### `POST /fetch-github`

Fetches GitHub content and returns parsed repository/code structure.

Request:

```json
{
  "url": "https://github.com/owner/repo"
}
```

Response:

```json
{
  "content": "README and repository scan text",
  "file_path": "README.md + repository scan",
  "language": "markdown",
  "is_pr": false,
  "symbols": {
    "functions": [],
    "classes": [],
    "line_count": 729,
    "language": "markdown",
    "imports": []
  }
}
```

Supported GitHub inputs:

```text
https://github.com/owner/repo
https://github.com/owner/repo/blob/main/path/to/file.py
https://github.com/owner/repo/pull/123
```

### `POST /generate`

Generates documentation and streams tokens as Server-Sent Events.

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

Stream frames:

```text
data: generated token
data: [TOKENS]128
data: [SCORE]{"coverage":90,"examples":85,"params":88,"edge_cases":75,"overall":85,"improvements":[]}
data: [DONE]
```

### `POST /chat`

Answers follow-up questions using the scanned source and generated report context.

Request:

```json
{
  "question": "Which file trains the BiGRU model and what proof do you have?",
  "source": "repository scan text",
  "report": "generated report text",
  "source_label": "README.md + repository scan",
  "history": []
}
```

Response:

```json
{
  "answer": "Direct answer: the BiGRU model is trained in `src/model_training/train_bigru.py`...",
  "citations": [
    {
      "label": "Repository scan: File: src/model_training/train_bigru.py part 1",
      "preview": "### File: src/model_training/train_bigru.py..."
    }
  ],
  "provider": "local"
}
```

## Inputs and Outputs

### Inputs

DocuMind supports:

- GitHub repository URLs.
- GitHub single-file URLs.
- GitHub pull request URLs.
- Uploaded files.
- Pasted code.
- OpenAPI YAML or JSON.
- Follow-up chatbot questions.

### Outputs

DocuMind can produce:

- generated README files
- inline documentation
- OpenAPI specs
- Confluence pages
- Docusaurus pages
- repository reports
- quality scores
- chatbot answers with citations

## Environment Variables

Create `.env` in the repository root for local backend development.

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

Provider behavior:

- `LLM_PROVIDER=auto`: prefer OpenRouter if configured, otherwise use available provider or local fallback.
- `LLM_PROVIDER=openai`: use OpenAI when `OPENAI_API_KEY` is configured.
- `OPENROUTER_API_KEY`: recommended for free or low-cost hosted models.
- No LLM key: generation/chat use the local fallback where supported.

Frontend local environment:

```text
VITE_API_URL=http://localhost:8000
```

On Hugging Face, the app runs same-origin through FastAPI, so the frontend does not need a separate public API URL.

## How To Run Locally

### Backend

From the repository root:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend URL:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Frontend URL:

```text
http://localhost:5173
```

## How To Use The App

1. Open the deployed app or local frontend.
2. Choose an input method:
   - GitHub URL
   - Upload
   - Paste code
   - OpenAPI
3. Load the source.
4. Select the output format.
5. Enable onboarding mode if the output should be beginner-friendly.
6. Enable self-critique if a quality score is needed.
7. Click **Generate docs**.
8. Use Preview, Raw, Diff view, or Score tabs.
9. Ask follow-up questions in the chatbot.
10. Copy or download the final output.

Example GitHub repo to test:

```text
https://github.com/Venkat-023/Longitudinal-Temporal-Disease-Progression
```

Example chatbot questions:

```text
Explain what this project does in detail for a new user.
Which file trains the BiGRU model and what proof do you have?
What are the dataset facts and model result facts from the README?
```

## Dockerization

This project includes Docker support for both local development and Hugging Face deployment.

### Local Docker Compose

Use Docker Compose to run frontend and backend as separate services:

```bash
docker compose up --build
```

Local Docker URLs:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
Health:   http://localhost:8000/health
```

Docker files:

```text
backend.Dockerfile    FastAPI backend image
frontend.Dockerfile   Vite frontend image
docker-compose.yml    Local multi-container orchestration
```

### Hugging Face Docker Deployment

Hugging Face Spaces does not run `docker compose` for the public app. It builds the root `Dockerfile`.

The root `Dockerfile`:

1. Uses a Python base image.
2. Installs Node.js.
3. Installs FastAPI backend dependencies.
4. Installs frontend dependencies.
5. Builds the frontend.
6. Serves the built frontend through FastAPI.
7. Runs the app on port `7860`, which Hugging Face exposes publicly.

The Space metadata at the top of this README tells Hugging Face:

```yaml
sdk: docker
app_port: 7860
```

Deployment URL:

```text
https://venkat-023-documind-ai.hf.space/
```

Space repository:

```text
https://huggingface.co/spaces/Venkat-023/DocuMind-Ai
```

Recommended Hugging Face secrets:

```text
OPENROUTER_API_KEY
OPENAI_API_KEY
GITHUB_TOKEN
LLM_PROVIDER
```

After changing secrets, restart the Space from the Hugging Face settings page.

## Error Handling

The backend returns structured `detail` messages so the frontend can display clear user-friendly errors.

Examples:

```json
{ "detail": "Cannot parse GitHub URL. Paste a direct file URL like github.com/owner/repo/blob/main/file.py" }
```

```json
{ "detail": "File too large (1200 lines). Maximum is 800 lines." }
```

```json
{ "detail": "Could not reach GitHub. Check the URL and try again." }
```

```json
{ "detail": "Rate limit hit. Wait 30 seconds and retry." }
```

## Verification Status

The deployed Hugging Face app was tested with:

```text
https://github.com/Venkat-023/Longitudinal-Temporal-Disease-Progression
```

Verified behavior:

- GitHub repo fetch works.
- Repository scan includes README and source files.
- Documentation generation works.
- Chatbot answers follow-up questions.
- Proof/facts questions return citations.
- Dataset/model metrics from README are extracted and reported.
- Hugging Face Space runs from Docker on port `7860`.

## Security Notes

- Do not commit `.env` files.
- Do not commit API keys.
- Store production keys as Hugging Face Space secrets.
- Rotate any key that has been pasted into chat, screenshots, logs, or commits.
- Use a GitHub token only when private repo access or higher rate limits are needed.

## Future Improvements

- Add a vector database for larger repositories.
- Add persistent chat sessions.
- Add PR creation for documentation changes.
- Add deeper TypeScript AST extraction.
- Add repository-wide dependency graph visualization.
- Add user authentication for private team deployments.

## License

Add a license before using this project in production or distributing it publicly.
