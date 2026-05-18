import sys
import os
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from starlette.testclient import TestClient

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


def _build_test_app(rag: object) -> FastAPI:
    """Minimal FastAPI app mirroring app.py endpoints without the static files mount."""

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Any]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag.session_manager.create_session()
            answer, sources = rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag.session_manager.sessions.pop(session_id, None)
        return {"status": "ok"}

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return test_app


@pytest.fixture()
def mock_rag():
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "test-session-001"
    rag.session_manager.sessions = {}
    rag.query.return_value = (
        "Test answer.",
        [{"label": "Course A - Lesson 1", "link": "https://example.com/1"}],
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    return rag


@pytest.fixture()
def client(mock_rag):
    app = _build_test_app(mock_rag)
    with TestClient(app) as c:
        yield c
