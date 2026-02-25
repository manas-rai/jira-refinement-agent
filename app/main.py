"""
Jira Refinement Agent — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.jira.mcp_client import mcp_jira_client

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan: startup + shutdown hooks."""
    logger.info("startup", service="jira-refinement-agent")
    # Start the MCP Jira client (spawns mcp-atlassian subprocess)
    await mcp_jira_client.start()
    yield
    # Shutdown: stop the MCP client
    await mcp_jira_client.stop()
    logger.info("shutdown", service="jira-refinement-agent")


app = FastAPI(
    title="Jira Refinement Agent",
    description=(
        "AI-powered Jira ticket refinement — turns rough tickets "
        "into sprint-ready specs via a conversational loop in comments."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(webhook_router)


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "healthy",
        "service": "jira-refinement-agent",
        "version": "0.2.0",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "mcp_connected": mcp_jira_client.is_connected,
        "jira_configured": bool(settings.JIRA_API_TOKEN),
        "llm_configured": bool(settings.OPENAI_API_KEY),
    }
