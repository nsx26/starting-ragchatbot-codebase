"""
Tests for CourseSearchTool.execute() and ToolManager.

Unit tests use a mocked VectorStore; regression tests use a real in-memory
ChromaDB with MockEmbeddingFunction to prove that MAX_RESULTS=0 is the root
cause of the "query failed" issue.
"""

import tempfile
from unittest.mock import MagicMock

import pytest

from search_tools import CourseSearchTool, ToolManager
from vector_store import VectorStore, SearchResults, MockEmbeddingFunction
from models import CourseChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_store(search_return: SearchResults) -> MagicMock:
    store = MagicMock(spec=VectorStore)
    store.search.return_value = search_return
    store.get_lesson_link.return_value = None
    return store


def _results_with_content(course_title="Test Course", lesson_number=1) -> SearchResults:
    return SearchResults(
        documents=["Content about the topic."],
        metadata=[{"course_title": course_title, "lesson_number": lesson_number, "chunk_index": 0}],
        distances=[0.1],
        error=None,
    )


def _empty_results() -> SearchResults:
    return SearchResults(documents=[], metadata=[], distances=[], error=None)


# ---------------------------------------------------------------------------
# 1. Formatted output contains course title, lesson number, document text
# ---------------------------------------------------------------------------

def test_execute_formats_course_title_lesson_and_text():
    tool = CourseSearchTool(_mock_store(_results_with_content("Python 101", 3)))
    output = tool.execute(query="what is python")
    assert "Python 101" in output
    assert "Lesson 3" in output
    assert "Content about the topic." in output


# ---------------------------------------------------------------------------
# 2. Empty SearchResults → "No relevant content found"
# ---------------------------------------------------------------------------

def test_execute_empty_results_returns_no_content_message():
    tool = CourseSearchTool(_mock_store(_empty_results()))
    output = tool.execute(query="mystery topic")
    assert "No relevant content found" in output


# ---------------------------------------------------------------------------
# 3. Empty + course_name → message includes filter value
# ---------------------------------------------------------------------------

def test_execute_empty_message_includes_course_name_filter():
    tool = CourseSearchTool(_mock_store(_empty_results()))
    output = tool.execute(query="anything", course_name="Advanced ML")
    assert "Advanced ML" in output


# ---------------------------------------------------------------------------
# 4. Empty + lesson_number → message includes lesson number
# ---------------------------------------------------------------------------

def test_execute_empty_message_includes_lesson_number_filter():
    tool = CourseSearchTool(_mock_store(_empty_results()))
    output = tool.execute(query="anything", lesson_number=7)
    assert "7" in output


# ---------------------------------------------------------------------------
# 5. SearchResults.error → execute() returns the error string verbatim
# ---------------------------------------------------------------------------

def test_execute_returns_error_string_from_search_results():
    error_msg = "Search error: n_results must be positive"
    tool = CourseSearchTool(_mock_store(SearchResults.empty(error_msg)))
    output = tool.execute(query="anything")
    assert output == error_msg


# ---------------------------------------------------------------------------
# 6. Successful search → last_sources populated with {label, link}
# ---------------------------------------------------------------------------

def test_execute_populates_last_sources_with_label_and_link():
    store = _mock_store(_results_with_content("RAG Course", 2))
    store.get_lesson_link.return_value = "https://example.com/lesson/2"
    tool = CourseSearchTool(store)
    tool.execute(query="embeddings")
    assert len(tool.last_sources) == 1
    src = tool.last_sources[0]
    assert "label" in src and "link" in src
    assert "RAG Course" in src["label"]
    assert "2" in src["label"]
    assert src["link"] == "https://example.com/lesson/2"


# ---------------------------------------------------------------------------
# 7. store.search() called with correct kwargs
# ---------------------------------------------------------------------------

def test_execute_passes_all_kwargs_to_store_search():
    store = _mock_store(_empty_results())
    tool = CourseSearchTool(store)
    tool.execute(query="neural nets", course_name="Deep Learning", lesson_number=4)
    store.search.assert_called_once_with(
        query="neural nets",
        course_name="Deep Learning",
        lesson_number=4,
    )


def test_execute_passes_none_for_omitted_optional_kwargs():
    store = _mock_store(_empty_results())
    tool = CourseSearchTool(store)
    tool.execute(query="transformers")
    store.search.assert_called_once_with(
        query="transformers",
        course_name=None,
        lesson_number=None,
    )


# ---------------------------------------------------------------------------
# 8. Regression A — real ChromaDB, max_results=0: returns error/empty (not content)
# ---------------------------------------------------------------------------

def test_regression_max_results_zero_returns_no_content():
    """
    ROOT CAUSE TEST: MAX_RESULTS=0 makes ChromaDB raise TypeError which
    VectorStore catches and wraps as SearchResults.error. The tool then
    returns that error string — never any real chunk content.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(tmp, "all-MiniLM-L6-v2", max_results=0, mock_mode=True)
        store.add_course_content([
            CourseChunk(
                content="Python is a programming language.",
                course_title="Intro to Python",
                lesson_number=1,
                chunk_index=0,
            )
        ])
        tool = CourseSearchTool(store)
        output = tool.execute(query="Python programming")

        # Chunk content must NOT appear — search should have failed
        assert "Python is a programming language." not in output
        # Should be an error message or the empty-results sentinel
        assert "Search error:" in output or "No relevant content found" in output, (
            f"Unexpected output with max_results=0: {output!r}"
        )


# ---------------------------------------------------------------------------
# 9. Regression B — real ChromaDB, max_results=5: returns content (fix works)
# ---------------------------------------------------------------------------

def test_regression_max_results_five_returns_chunk_content():
    """
    FIX VERIFICATION: Changing MAX_RESULTS to 5 restores correct behaviour.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(tmp, "all-MiniLM-L6-v2", max_results=5, mock_mode=True)
        store.add_course_content([
            CourseChunk(
                content="Python is a programming language.",
                course_title="Intro to Python",
                lesson_number=1,
                chunk_index=0,
            )
        ])
        tool = CourseSearchTool(store)
        output = tool.execute(query="Python programming")

        assert "Python is a programming language." in output, (
            f"Expected chunk content with max_results=5, got: {output!r}"
        )
