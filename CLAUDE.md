# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ReAct (Reasoning + Acting) research agent built with LangChain. The agent uses a manual while-loop implementation (not LangGraph's StateGraph) to perform web search and calculations. It uses Alibaba Cloud DashScope's Qwen3.5-plus model via OpenAI-compatible API.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the ReAct agent (interactive)
python simple_react.py

# Run tests in Jupyter notebook
jupyter notebook test.ipynb
```

## Architecture

```
simple_react.py          # Main ReAct agent with manual observe->plan->act loop
src/
  config.py              # LLM configuration (DashScope API, Qwen3.5-plus model)
  tools.py               # Tool definitions: search_tool (Tavily), calculator_tool
```

**ReAct Loop Flow** (simple_react.py):
1. **Observe**: Display current input and message history
2. **Plan**: Call LLM with tools bound
3. **Act**: If LLM requests tools, execute them and loop back to Observe; otherwise return response
4. Max 10 iterations to prevent infinite loops

**AgentState** (TypedDict):
- `input`: Current user question
- `messages`: Conversation history (HumanMessage, AIMessage, ToolMessage)
- `step_count`: Iteration counter (max 10)

## API Configuration

Environment variables are loaded from `config.env`:
- `DASHSCOPE_API_KEY` - Alibaba Cloud DashScope (required)
- `TAVILY_API_KEY` - Tavily web search (required)
- `COHERE_API_KEY` - Cohere reranking (optional)

## Key Dependencies

- **langchain-openai** - LLM interface (DashScope compatible)
- **tavily-python** - Web search tool
- **python-dotenv** - Environment variable loading

## Notes

- System prompt is in Chinese
- `simple_react.py` includes UTF-8 encoding setup for Windows stdout/stderr/stdin (lines 6-9)
- `calculator_tool` validates input characters before eval() for security
- `src/config.py` exports `llm` directly; the `get_llm()` function is defined but unused
- Environment is loaded from `config.env` (also copies to `.env` which is gitignored)
