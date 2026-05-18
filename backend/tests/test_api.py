"""Tests for FastAPI endpoints: /api/query, /api/courses, /api/session/{id}."""


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

def test_query_returns_200_with_answer_sources_session(client):
    resp = client.post("/api/query", json={"query": "What is RAG?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Test answer."
    assert isinstance(body["sources"], list) and len(body["sources"]) > 0
    assert "session_id" in body


def test_query_without_session_id_generates_one(client, mock_rag):
    resp = client.post("/api/query", json={"query": "What is RAG?"})
    assert resp.status_code == 200
    mock_rag.session_manager.create_session.assert_called_once()
    assert resp.json()["session_id"] == "test-session-001"


def test_query_with_session_id_preserves_it(client, mock_rag):
    resp = client.post("/api/query", json={"query": "Hello", "session_id": "my-session"})
    assert resp.status_code == 200
    mock_rag.session_manager.create_session.assert_not_called()
    assert resp.json()["session_id"] == "my-session"


def test_query_calls_rag_with_correct_args(client, mock_rag):
    client.post("/api/query", json={"query": "What is a vector DB?", "session_id": "s1"})
    mock_rag.query.assert_called_once_with("What is a vector DB?", "s1")


def test_query_rag_error_returns_500(client, mock_rag):
    mock_rag.query.side_effect = RuntimeError("DB unavailable")
    resp = client.post("/api/query", json={"query": "crash?"})
    assert resp.status_code == 500
    assert "DB unavailable" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

def test_get_courses_returns_200_with_stats(client):
    resp = client.get("/api/courses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_courses"] == 2
    assert body["course_titles"] == ["Course A", "Course B"]


def test_get_courses_analytics_error_returns_500(client, mock_rag):
    mock_rag.get_course_analytics.side_effect = RuntimeError("Analytics failed")
    resp = client.get("/api/courses")
    assert resp.status_code == 500
    assert "Analytics failed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

def test_delete_session_removes_it_and_returns_ok(client, mock_rag):
    mock_rag.session_manager.sessions = {"sess-1": {"history": []}}
    resp = client.delete("/api/session/sess-1")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert "sess-1" not in mock_rag.session_manager.sessions


def test_delete_nonexistent_session_returns_ok(client):
    resp = client.delete("/api/session/does-not-exist")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
