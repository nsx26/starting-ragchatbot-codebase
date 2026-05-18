"""
Tests for AIGenerator.

Unit tests for mock mode and real-API mode. Real-API tests patch
`ai_generator.anthropic.Anthropic` (the module-level import target).
"""

from unittest.mock import MagicMock, patch

from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Helpers for building mock Anthropic responses
# ---------------------------------------------------------------------------

def _text_response(text: str) -> MagicMock:
    response = MagicMock()
    response.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = text
    response.content = [block]
    return response


def _tool_use_response(name: str, tool_id: str, input_dict: dict) -> MagicMock:
    response = MagicMock()
    response.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_dict
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# 1. api_key="" → mock_mode=True; non-empty → mock_mode=False
# ---------------------------------------------------------------------------

def test_empty_api_key_activates_mock_mode():
    gen = AIGenerator(api_key="", model="claude-sonnet-4-20250514")
    assert gen.mock_mode is True


def test_nonempty_api_key_disables_mock_mode():
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="sk-test", model="claude-sonnet-4-20250514")
    assert gen.mock_mode is False


# ---------------------------------------------------------------------------
# 2. Mock mode returns MOCK_RESPONSE
# ---------------------------------------------------------------------------

def test_mock_mode_returns_mock_response():
    gen = AIGenerator(api_key="", model="claude-sonnet-4-20250514")
    result = gen.generate_response("What courses are available?")
    assert result == AIGenerator.MOCK_RESPONSE
    assert "Mock mode" in result


# ---------------------------------------------------------------------------
# 3. Mock mode does NOT call tool_manager even when tools are provided
# ---------------------------------------------------------------------------

def test_mock_mode_never_calls_tool_manager():
    gen = AIGenerator(api_key="", model="claude-sonnet-4-20250514")
    tm = MagicMock()
    tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
    gen.generate_response("search for Python", tools=tools, tool_manager=tm)
    tm.execute_tool.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Real mode: tools list appears in the first API call kwargs
# ---------------------------------------------------------------------------

def test_real_mode_passes_tools_to_api():
    with patch("ai_generator.anthropic.Anthropic") as MockA:
        MockA.return_value.messages.create.return_value = _text_response("Answer.")
        gen = AIGenerator(api_key="sk-test", model="claude-sonnet-4-20250514")
        tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
        gen.generate_response("What is RAG?", tools=tools, tool_manager=MagicMock())
        kwargs = MockA.return_value.messages.create.call_args_list[0][1]
        assert "tools" in kwargs
        assert kwargs["tools"] == tools


# ---------------------------------------------------------------------------
# 5. Real mode tool_use: execute_tool called with correct name + input
# ---------------------------------------------------------------------------

def test_real_mode_tool_use_calls_execute_tool_correctly():
    tool_input = {"query": "Python basics", "course_name": "Intro"}
    with patch("ai_generator.anthropic.Anthropic") as MockA:
        client = MockA.return_value
        client.messages.create.side_effect = [
            _tool_use_response("search_course_content", "id_001", tool_input),
            _text_response("Python answer."),
        ]
        gen = AIGenerator(api_key="sk-test", model="claude-sonnet-4-20250514")
        tm = MagicMock()
        tm.execute_tool.return_value = "chunk content"
        tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
        gen.generate_response("Tell me about Python", tools=tools, tool_manager=tm)
    tm.execute_tool.assert_called_once_with("search_course_content", **tool_input)


# ---------------------------------------------------------------------------
# 6. Real mode tool_use: API called twice total
# ---------------------------------------------------------------------------

def test_real_mode_tool_use_makes_two_api_calls():
    with patch("ai_generator.anthropic.Anthropic") as MockA:
        client = MockA.return_value
        client.messages.create.side_effect = [
            _tool_use_response("search_course_content", "id_002", {"query": "RAG"}),
            _text_response("RAG answer."),
        ]
        gen = AIGenerator(api_key="sk-test", model="claude-sonnet-4-20250514")
        tm = MagicMock()
        tm.execute_tool.return_value = "result"
        tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
        gen.generate_response("Explain RAG", tools=tools, tool_manager=tm)
    assert client.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# 7. Real mode end_turn: returns content[0].text directly, no tool calls
# ---------------------------------------------------------------------------

def test_real_mode_end_turn_returns_text_directly():
    expected = "Direct answer here."
    with patch("ai_generator.anthropic.Anthropic") as MockA:
        MockA.return_value.messages.create.return_value = _text_response(expected)
        gen = AIGenerator(api_key="sk-test", model="claude-sonnet-4-20250514")
        tm = MagicMock()
        result = gen.generate_response("2 + 2?", tool_manager=tm)
    assert result == expected
    tm.execute_tool.assert_not_called()


# ---------------------------------------------------------------------------
# 8. Real mode tool_use: returns the SECOND response's text
# ---------------------------------------------------------------------------

def test_real_mode_tool_use_returns_synthesized_final_text():
    final_text = "Synthesized answer about embeddings."
    with patch("ai_generator.anthropic.Anthropic") as MockA:
        client = MockA.return_value
        client.messages.create.side_effect = [
            _tool_use_response("search_course_content", "id_003", {"query": "embeddings"}),
            _text_response(final_text),
        ]
        gen = AIGenerator(api_key="sk-test", model="claude-sonnet-4-20250514")
        tm = MagicMock()
        tm.execute_tool.return_value = "embedding content"
        tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
        result = gen.generate_response("What are embeddings?", tools=tools, tool_manager=tm)
    assert result == final_text
