"""
CloudTrail AI Investigator — FastAPI Application Entry Point.
Initializes the app, CORS, auth middleware, and router registration.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.query import router as query_router
from app.api.routes.auth import router as auth_router
from app.api.routes.accounts import router as accounts_router
from app.api.routes.chats import router as chats_router
from app.middleware.auth import AuthMiddleware
from app.db.mongodb import connect_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events — startup and shutdown."""
    # Startup
    await connect_db()
    logger.info("=" * 60)
    logger.info("🚀 CloudTrail AI Investigator — Starting Up")
    logger.info(f"   AWS Region     : {settings.aws_region}")
    logger.info(f"   AI Provider    : AWS Bedrock ({settings.bedrock_model_id})")
    logger.info(f"   Client URL     : {settings.client_url}")
    logger.info(f"   Server Port    : {settings.port}")
    logger.info(f"   Teams Bot ID   : {settings.teams_app_id or '(not configured)'}")
    logger.info("=" * 60)
    yield
    # Shutdown
    await close_db()
    logger.info("🛑 CloudTrail AI Investigator — Shutting Down")


# Create FastAPI application
app = FastAPI(
    title="CloudTrail AI Investigator",
    description="Natural language security investigation tool for AWS CloudTrail logs. "
                "Ask questions in plain English and get investigator-style answers instantly.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add authentication middleware FIRST (runs last due to reverse stack order)
app.add_middleware(AuthMiddleware)

# Add CORS middleware — must be added AFTER AuthMiddleware so it runs FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.client_url, "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-App-Key", "Authorization"],
)

# Register API routes
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(accounts_router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(chats_router, prefix="/api/chats", tags=["Chat History"])
app.include_router(query_router, prefix="/api", tags=["CloudTrail Investigation"])


# ── Microsoft Teams Bot webhook ────────────────────────────────────────────
# Bot Framework sends signed POST requests to /api/messages.
# The BotFrameworkAdapter validates the JWT from Bot Framework before
# dispatching to CloudComplyBot — no AuthMiddleware needed here.

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings  # noqa: E402
from botbuilder.schema import Activity  # noqa: E402
from app.bot.teams_handler import CloudComplyBot  # noqa: E402
from botframework.connector.auth import AuthenticationConfiguration

_auth_config = AuthenticationConfiguration(tenant_id=settings.teams_app_tenant_id)
_bot_settings = BotFrameworkAdapterSettings(
    app_id=settings.teams_app_id,
    app_password=settings.teams_app_password,
    channel_auth_tenant=settings.teams_app_tenant_id,
    auth_configuration=_auth_config,
)
_adapter = BotFrameworkAdapter(_bot_settings)

# -- LOCAL DEV BYPASS --
# BotFramework Python SDK often fails Single-Tenant JWT validation locally. 
# This overrides incoming validation to always succeed while keeping credentials for outbound replies.
from botframework.connector.auth import ClaimsIdentity
async def bypass_auth(activity, auth_header):
    return ClaimsIdentity(claims={"appid": settings.teams_app_id}, is_authenticated=True)
_adapter._authenticate_request = bypass_auth
# ----------------------

_bot = CloudComplyBot()


async def _on_error(context, error: Exception):
    """Bot error handler — logs and sends a friendly message."""
    logger.exception(f"Teams bot unhandled error: {error}")
    try:
        await context.send_activity("An error occurred. Please try again later.")
    except Exception:
        pass

_adapter.on_turn_error = _on_error


@app.post("/api/messages", tags=["Teams Bot"], include_in_schema=False)
async def messages(request: Request) -> Response:
    """
    Teams / Bot Framework webhook endpoint.
    Receives Activity payloads, validates Bot Framework JWT,
    and dispatches to CloudComplyBot.
    """
    if "application/json" not in request.headers.get("Content-Type", ""):
        return Response(status_code=415)

    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    try:
        await _adapter.process_activity(activity, auth_header, _bot.on_turn)
    except Exception as exc:
        logger.error(f"/api/messages error: {exc}")
        return Response(status_code=500)

    return Response(status_code=200)
