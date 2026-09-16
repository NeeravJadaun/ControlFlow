"""ControlFlow FastAPI application entrypoint."""

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    accounts,
    audit,
    auth,
    cases,
    controls,
    dashboards,
    documents,
    entities,
    financial,
    health,
    users,
    workflows,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, correlation_id_ctx, logger

settings = get_settings()

configure_logging()

app = FastAPI(
    title="ControlFlow API",
    description=(
        "Operations and Compliance Management Platform — configurable records, "
        "cases, documents, workflows, controls, and audit trails. Synthetic "
        "demo data only; not for production use."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", uuid.uuid4().hex[:16])
    token = correlation_id_ctx.set(correlation_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        correlation_id_ctx.reset(token)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Correlation-Id"] = correlation_id
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(entities.router, prefix="/api/entities", tags=["entities"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(controls.router, prefix="/api/controls", tags=["controls"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(dashboards.router, prefix="/api/dashboards", tags=["dashboards"])
app.include_router(financial.router, prefix="/api/financial", tags=["financial"])
