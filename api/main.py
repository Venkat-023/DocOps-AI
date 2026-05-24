from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
