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
        return Response(
            content=body,
            status_code=upstream_response.status_code,
            headers=headers,
            media_type=content_type,
        )
