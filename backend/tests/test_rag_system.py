"""
Integration-style tests for RAGSystem.

Uses a minimal _TestConfig dataclass and real in-memory ChromaDB (mock_mode=True)
to verify that the MAX_RESULTS=0 misconfiguration is the root cause of failures,
and that changing it to 5 restores correct behaviour.
"""

import tempfile
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from rag_system import RAGSystem
from models import CourseChunk


# ---------------------------------------------------------------------------
# Minimal config — mirrors every field accessed in RAGSystem.__init__
# ---------------------------------------------------------------------------

@dataclass
class _TestConfig:
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    MOCK_MODE: bool = True
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "./chroma_db"


_CHUNK = CourseChunk(
    content="Vector databases store embeddings for fast similarity search.",
    course_title="Intro to Vector DBs",
    lesson_number=1,
    chunk_index=0,
)


# ---------------------------------------------------------------------------
# 1. MAX_RESULTS=0, real ChromaDB: search_tool returns no chunk content
# ---------------------------------------------------------------------------

def test_max_results_zero_search_returns_no_chunk_content():
    """
    Proves the root cause: with MAX_RESULTS=0 the search tool never returns
    actual content, so the AI has nothing to synthesize.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cfg = _TestConfig(MAX_RESULTS=0, CHROMA_PATH=tmp)
        rag = RAGSystem(cfg)
        rag.vector_store.add_course_content([_CHUNK])

        result = rag.search_tool.execute(query="vector database embeddings")

        assert _CHUNK.content not in result
        assert "Search error:" in result or "No relevant content found" in result, (
            f"Expected error or empty message, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# 2. MAX_RESULTS=5, real ChromaDB: search_tool returns chunk content
# ---------------------------------------------------------------------------

def test_max_results_five_search_returns_chunk_content():
    """Fix verification: MAX_RESULTS=5 makes the search tool return real content."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cfg = _TestConfig(MAX_RESULTS=5, CHROMA_PATH=tmp)
        rag = RAGSystem(cfg)
        rag.vector_store.add_course_content([_CHUNK])

        result = rag.search_tool.execute(query="vector database embeddings")

        assert _CHUNK.content in result, (
            f"Expected chunk content with MAX_RESULTS=5, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# 3. Config value propagates correctly to VectorStore.max_results
# ---------------------------------------------------------------------------

def test_max_results_zero_propagates_to_vector_store():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        rag = RAGSystem(_TestConfig(MAX_RESULTS=0, CHROMA_PATH=tmp))
        assert rag.vector_store.max_results == 0


def test_max_results_five_propagates_to_vector_store():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        rag = RAGSystem(_TestConfig(MAX_RESULTS=5, CHROMA_PATH=tmp))
        assert rag.vector_store.max_results == 5


# ---------------------------------------------------------------------------
# 4. query() in mock mode returns a non-empty string
# ---------------------------------------------------------------------------

def test_rag_query_mock_mode_returns_nonempty_string():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        rag = RAGSystem(_TestConfig(MAX_RESULTS=5, CHROMA_PATH=tmp))
        response, sources = rag.query("What courses are available?")
        assert isinstance(response, str) and len(response) > 0


# ---------------------------------------------------------------------------
# 5. query() non-mock mode: sources from tool_manager are returned
# ---------------------------------------------------------------------------

def test_rag_query_non_mock_returns_tool_manager_sources():
    expected_sources = [
        {"label": "Intro to Python - Lesson 1", "link": "https://example.com/1"},
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        # Use MOCK_MODE=True during init so VectorStore uses MockEmbeddingFunction
        # (avoids SSL calls to HuggingFace Hub on restricted networks).
        with patch("ai_generator.anthropic.Anthropic"):
            rag = RAGSystem(_TestConfig(
                MAX_RESULTS=5, MOCK_MODE=True,
                ANTHROPIC_API_KEY="sk-test", CHROMA_PATH=tmp,
            ))
        # Flip to False so query() takes the non-mock sources branch
        rag.config.MOCK_MODE = False
        rag.ai_generator.generate_response = MagicMock(return_value="Synthesized answer.")
        rag.tool_manager.get_last_sources = MagicMock(return_value=expected_sources)

        response, sources = rag.query("Tell me about Python")

    assert response == "Synthesized answer."
    assert sources == expected_sources


# ---------------------------------------------------------------------------
# 6. query() mock mode uses hardcoded sources, not tool_manager
# ---------------------------------------------------------------------------

def test_rag_query_mock_mode_uses_hardcoded_sources_not_tool_manager():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        rag = RAGSystem(_TestConfig(MAX_RESULTS=5, MOCK_MODE=True, CHROMA_PATH=tmp))
        rag.tool_manager.get_last_sources = MagicMock(return_value=[])

        _response, sources = rag.query("anything")

        # Mock mode should return the hardcoded MCP lesson links
        assert isinstance(sources, list) and len(sources) > 0
        rag.tool_manager.get_last_sources.assert_not_called()
