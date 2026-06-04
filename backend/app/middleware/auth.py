"""
Authentication middleware — validates JWT Bearer token on API routes.
"""

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import security

logger = logging.getLogger(__name__)

# Routes exempt from authentication
EXEMPT_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc", "/api/messages"}
EXEMPT_PREFIXES = {"/api/auth/"}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT Bearer token on all /api/* routes.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always allow CORS preflight requests through
        if request.method == "OPTIONS":
            return await call_next(request)

        # Allow exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)
            
        for prefix in EXEMPT_PREFIXES:
            if path.startswith(prefix) and path != "/api/auth/me":
                return await call_next(request)

        # Only check auth on /api/* routes
        if path.startswith("/api"):
            auth_header = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning(f"Missing Authorization header for {request.method} {path}")
                return Response(
                    content=json.dumps({
                        "detail": "Missing or invalid Authorization header"
                    }),
                    status_code=401,
                    media_type="application/json",
                )
                
            token = auth_header.split(" ")[1]
            try:
                payload = security.decode_access_token(token)
                request.state.user = payload
            except Exception as e:
                logger.warning(f"Invalid token for {request.method} {path}: {str(e)}")
                return Response(
                    content=json.dumps({
                        "detail": "Invalid or expired token"
                    }),
                    status_code=401,
                    media_type="application/json",
                )

        return await call_next(request)
