from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import httpx

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


@app.api_route("/{path:path}", methods=["GET", "HEAD", "OPTIONS"])
async def frontend_proxy(path: str):
    upstream = f"http://127.0.0.1:5173/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        request = client.build_request("GET", upstream)
        upstream_response = await client.send(request, stream=True)

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
        return Response(
            content=body,
            status_code=upstream_response.status_code,
            headers=headers,
            media_type=upstream_response.headers.get("content-type"),
        )
