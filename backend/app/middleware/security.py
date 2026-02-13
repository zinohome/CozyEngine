"""Security Headers Middleware."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config.manager import get_config

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    Reference: OWASP Secure Headers Project
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.config = get_config()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        
        # 1. HSTS (Strict-Transport-Security)
        # Enforce HTTPS for 1 year, include subdomains
        # Skip for local development if needed, but good practice to have.
        # Check config environment?
        if self.config.environment != "development":
             response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # 2. X-Content-Type-Options
        # Prevent MIME-sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 3. X-Frame-Options
        # Prevent Clickjacking (Default to DENY, or SAMEORIGIN if needed)
        response.headers["X-Frame-Options"] = "DENY"
        
        # 4. Content-Security-Policy
        # For API, usually we don't serve HTML, but good to set default
        # "default-src 'none'" is strict for APIs. 
        # But if we serve Swagger UI (/docs), we need to allow scripts/styles.
        # We can loosely check path or just set a permissive default for now.
        # Let's use a safe default that allows Swagger:
        # "default-src 'self'; script-src 'self' 'unsafe-inline' (for Swagger); style-src 'self' 'unsafe-inline';"
        # For pure API, "frame-ancestors 'none'" is key.
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        
        # 5. Referrer-Policy
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 6. Permissions-Policy
        # Disable sensitive features
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        return response
