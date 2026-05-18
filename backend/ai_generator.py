import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **Up to 2 sequential searches per query** — only perform a second search if the first result was insufficient to answer the question
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    MOCK_RESPONSE = """*(Mock mode — no API key set)*

Here is an overview of the courses available in this assistant:

### 1. Building Toward Computer Use with Anthropic
**Instructor:** Colt Steele
Topics covered: API requests, multimodal image analysis, prompting techniques, tool use, and building computer use agents.

### 2. MCP: Build Rich-Context AI Apps with Anthropic
**Instructor:** Elie Schoppik
Topics covered: MCP client-server architecture, building MCP-compatible chatbots, connecting to third-party MCP servers, and remote deployment.

### 3. Advanced Retrieval for AI with Chroma
**Instructor:** Anton Troynikov
Topics covered: Query expansion, cross-encoder reranking, embedding adaptation, and cutting-edge RAG techniques.

### 4. Prompt Compression and Query Optimization
**Instructor:** Richmond Alake
Topics covered: Pre- and post-filtering, projection, reranking, and prompt compression to reduce LLM serving costs.

> Add `ANTHROPIC_API_KEY` to your `.env` file to enable real AI responses tailored to your query."""

    MAX_TOOL_ROUNDS = 2

    def __init__(self, api_key: str, model: str):
        self.mock_mode = not api_key
        if not self.mock_mode:
            self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        if self.mock_mode:
            return self.MOCK_RESPONSE

        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager, rounds_remaining: int = MAX_TOOL_ROUNDS - 1):
        """
        Handle execution of tool calls and get follow-up response.
        Recurses up to MAX_TOOL_ROUNDS - 1 additional times when Claude requests
        another tool call, then forces a final no-tools call.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters (must include "messages" and "system")
            tool_manager: Manager to execute tools
            rounds_remaining: How many more tool-calling rounds are permitted after this one

        Returns:
            Final response text after tool execution
        """
        messages = base_params["messages"].copy()
        messages.append({"role": "assistant", "content": initial_response.content})

        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name,
                    **content_block.input
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        follow_up_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
        }

        if rounds_remaining > 0:
            follow_up_params["tools"] = base_params["tools"]
            follow_up_params["tool_choice"] = {"type": "auto"}

        follow_up_response = self.client.messages.create(**follow_up_params)

        if follow_up_response.stop_reason == "tool_use" and rounds_remaining > 0:
            return self._handle_tool_execution(
                follow_up_response, follow_up_params, tool_manager, rounds_remaining - 1
            )

        return follow_up_response.content[0].text