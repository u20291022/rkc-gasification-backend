import time
import uuid
from typing import Callable, List
from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.logging import get_logger, categorize_log, LogCategory
from app.core.config import settings
import json
from fastapi.responses import JSONResponse, StreamingResponse

logger = get_logger("middleware")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.response_body_size_limit = 10000  # Limit response body size for logging

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.ENABLE_REQUEST_LOGGING:
            return await call_next(request)
            
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        query_params = dict(request.query_params)
        headers = self._get_relevant_headers(request)
        request_body = {}
        
        if request.method != "GET":
            try:
                body_bytes = await request.body()
                request.scope["_body"] = body_bytes  # Save for later reuse
                if len(body_bytes) > 0:
                    try:
                        body_str = body_bytes.decode('utf-8')
                        if len(body_str) > 1000:  # Limit long bodies
                            request_body = {"content": body_str[:1000] + "... (truncated)"}
                        else:
                            try:
                                request_body = json.loads(body_str)
                            except:
                                request_body = {"content": body_str}
                    except:
                        request_body = {"content": "[binary data]"}
            except:
                request_body = {"error": "Failed to read request body"}
        
        logger.info(
            categorize_log(f"Request started: {request.method} {request.url.path}", LogCategory.HTTP),
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "query_params": query_params,
                "headers": headers,
                "request_body": request_body
            }
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Capture response body for logging in files
            response_body = await self._get_response_body(response)
            
            logger.info(
                categorize_log(f"Request completed: {request.method} {request.url.path}", LogCategory.HTTP),
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "processing_time_ms": round(process_time * 1000, 2),
                    "client_ip": client_ip,
                    "response_body": response_body,
                    "response_headers": dict(response.headers),
                }
            )
            
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                categorize_log(f"Request failed: {request.method} {request.url.path}", LogCategory.ERROR),
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "processing_time_ms": round(process_time * 1000, 2),
                    "client_ip": client_ip,
                    "query_params": query_params,
                }
            )
            raise
    
    async def _get_response_body(self, response: Response) -> dict:
        """Extract the response body for logging."""
        try:
            if isinstance(response, JSONResponse):
                # For JSON responses, we can directly access the body
                if len(response.body) > self.response_body_size_limit:
                    return {"content": "[response too large to log]"}
                try:
                    body_str = response.body.decode('utf-8')
                    return json.loads(body_str)
                except:
                    return {"content": body_str[:self.response_body_size_limit] + "... (truncated)" if len(body_str) > self.response_body_size_limit else body_str}
            elif isinstance(response, StreamingResponse):
                return {"content": "[streaming response]"}
            else:
                # For other response types, we may not be able to get the body
                return {"type": str(type(response)), "content": "[response body not captured]"}
        except Exception as e:
            return {"error": f"Failed to capture response body: {str(e)}"}
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        client_host = request.client.host if request.client else None
        forwarded_for = request.headers.get("X-Forwarded-For")
        
        if forwarded_for:
            # Get the first IP in the chain which is usually the client's real IP
            return forwarded_for.split(",")[0].strip()
        return client_host or "unknown"
    
    def _get_relevant_headers(self, request: Request) -> dict:
        """Extract relevant headers from request for logging."""
        headers = dict(request.headers)
        # Filter out sensitive headers
        sensitive_headers = ['authorization', 'cookie', 'set-cookie']
        filtered_headers = {}
        
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                filtered_headers[key] = "[REDACTED]"
            else:
                filtered_headers[key] = value
                
        return filtered_headers

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            request.scope["client"] = (forwarded_for.split(",")[0].strip(), request.scope["client"][1])
        
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto
        
        response = await call_next(request)
        return response

def setup_middlewares(app: FastAPI):
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ProxyHeadersMiddleware)
    setup_trusted_host_middleware(app)
    setup_cors_middleware(app)

def setup_trusted_host_middleware(app: FastAPI):
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["*"]
    )

def setup_cors_middleware(app: FastAPI, 
                         allow_origins: List[str] = ["*"],
                         allow_methods: List[str] = ["GET", "POST"]):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=allow_methods,
        allow_headers=["*"],
    )
