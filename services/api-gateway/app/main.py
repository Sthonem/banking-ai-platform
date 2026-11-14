import asyncio
import os

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request, Response, status

from banking_common.config import get_settings
from banking_common.observability import configure_observability
from banking_common.security import decode_token

app = FastAPI(title="api-gateway")
configure_observability(app, "api-gateway")

settings = get_settings()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)
ONBOARDING_URL = os.getenv("ONBOARDING_URL", "http://localhost:8001")
TRANSACTION_URL = os.getenv("TRANSACTION_URL", "http://localhost:8002")
PUBLIC_PATHS = {"/health", "/onboarding/auth/login", "/docs", "/openapi.json", "/metrics"}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    key = f"rate:{client}:{request.url.path}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 60)
    if count > settings.rate_limit_per_minute:
        return Response("Rate limit exceeded", status_code=status.HTTP_429_TOO_MANY_REQUESTS)
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


async def proxy(request: Request, base_url: str, prefix: str) -> Response:
    target_path = request.url.path.removeprefix(prefix)
    target_url = f"{base_url}{target_path}"
    body = await request.body()
    headers = {key: value for key, value in request.headers.items() if key.lower() != "host"}
    headers["x-correlation-id"] = getattr(request.state, "correlation_id", "")
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=2.0)) as client:
        for attempt in range(3):
            try:
                upstream = await client.request(
                    request.method,
                    target_url,
                    params=request.query_params,
                    content=body,
                    headers=headers,
                )
                if upstream.status_code < 500:
                    break
            except httpx.HTTPError as exc:
                last_error = exc
            await asyncio.sleep(0.1 * (attempt + 1))
        else:
            if last_error:
                raise HTTPException(status_code=502, detail=f"Upstream unavailable: {last_error}") from last_error
            raise HTTPException(status_code=502, detail="Upstream returned repeated server errors")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


def auth_guard(request: Request) -> dict | None:
    if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs"):
        return None
    if request.url.path == "/onboarding/users" and request.method == "POST":
        return None
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return decode_token(token)


@app.api_route("/onboarding/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def onboarding_proxy(request: Request) -> Response:
    auth_guard(request)
    return await proxy(request, ONBOARDING_URL, "/onboarding")


@app.api_route("/transactions", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/transactions/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def transaction_proxy(request: Request) -> Response:
    auth_guard(request)
    return await proxy(request, TRANSACTION_URL, "")
