"""Read-only FastAPI service in front of SQLite."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.db import db
from config import settings

app = FastAPI(
    title="StatShift API",
    description="Local read-only API over SQLite. Write operations are blocked.",
    version="0.1.0",
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class DocumentSummary(BaseModel):
    id: int
    title: str
    category: str
    content: str
    created_at: str
    score: float | None = None


class HealthResponse(BaseModel):
    status: str
    db_path: str
    read_only: bool = True


@app.middleware("http")
async def block_writes(request: Request, call_next):
    if request.method in WRITE_METHODS:
        return JSONResponse(
            status_code=405,
            content={
                "detail": (
                    "Write operations are disabled. "
                    "This API only exposes read access to SQLite."
                )
            },
        )
    return await call_next(request)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if not settings.db_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Database not found at {settings.db_path}. Run: python scripts/init_db.py",
        )
    return HealthResponse(status="ok", db_path=str(settings.db_path))


@app.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    category: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    return db.list_documents(category=category, limit=limit, offset=offset)


@app.get("/documents/{doc_id}", response_model=DocumentSummary)
def get_document(doc_id: int) -> dict[str, Any]:
    document = db.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.get("/search", response_model=list[DocumentSummary])
def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(5, ge=1, le=20),
) -> list[dict[str, Any]]:
    return db.search_documents(q, limit=limit)


@app.get("/categories")
def list_categories() -> dict[str, list[str]]:
    return {"categories": db.list_categories()}
