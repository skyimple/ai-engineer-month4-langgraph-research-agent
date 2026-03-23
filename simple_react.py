"""Simple ReAct Agent - Manual while loop implementation."""
import os
import sys
import io

# Set UTF-8 encoding for stdout/stderr/stdin
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')


def sanitize_string(s: str) -> str:
    """Remove surrogate characters that cause encoding errors."""
    return s.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')

from dotenv import load_dotenv
from typing import TypedDict
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

# Load environment variables
load_dotenv('config.env')

from src.config import llm
from src.tools import search_tool, calculator_tool

# Define Agent State
class AgentState(TypedDict):
    input: str
    messages: list
    step_count: int


# System prompt
SYSTEM_PROMPT = """你是一个有帮助的助手。当用户询问天气、信息查找、计算等问题时，必须使用对应的工具。
你有以下工具可用：
- search_tool: 用于搜索网络信息
- calculator_tool: 用于数学计算

当需要查找信息时，直接调用 search_tool 即可。"""

# Available tools
tools = [search_tool, calculator_tool]

# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)


def call_llm(state: AgentState) -> AgentState:
    """Call the LLM with the current state and return updated state."""
    print("\n--- LLM Thinking ---")

    # Build messages for the LLM
    messages = [HumanMessage(content=SYSTEM_PROMPT)]

    # Add conversation history
    for msg in state["messages"]:
        messages.append(msg)

    # Add the current input
    messages.append(HumanMessage(content=f"User question: {state['input']}"))

    # Invoke LLM with tools
    response = llm_with_tools.invoke(messages)

    # Add response to messages
    state["messages"].append(response)

    return state


def execute_tool_call(state: AgentState) -> AgentState:
    """Execute tool calls from the last LLM response."""
    last_message = state["messages"][-1]

    # Check if there are tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["args"]

            print(f"\n--- Action ---")
            print(f"Tool: {tool_name}")
            print(f"Input: {tool_input}")

            # Find and execute the tool
            for t in tools:
                if t.name == tool_name:
                    result = t.invoke(tool_input)
                    print(f"Result: {result}")

                    # Add tool result to messages
                    tool_msg = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    )
                    state["messages"].append(tool_msg)
                    break
    else:
        print("\n--- Action ---")
        print("No tool calls - responding directly to user")
        print(f"Response: {last_message.content if hasattr(last_message, 'content') else last_message}")

    return state


def main():
    """Main agent loop."""
    print("=" * 60)
    print("Simple ReAct Agent - Observe -> Plan -> Act Loop")
    print("=" * 60)

    # Initialize state
    state: AgentState = {
        "input": "",
        "messages": [],
        "step_count": 0
    }

    # Get user input
    user_input = input("\nEnter your question (or 'quit' to exit): ")
    if user_input.lower() == 'quit':
        print("Goodbye!")
        return

    state["input"] = sanitize_string(user_input)

    # Main loop
    max_steps = 10
    while state["step_count"] < max_steps:
        state["step_count"] += 1

        print("\n" + "=" * 60)
        print(f"Step {state['step_count']}")
        print("=" * 60)

        # Observe
        print("\n--- Observe ---")
        print(f"Input: {state['input']}")
        print(f"Messages so far: {len(state['messages'])}")

        # Plan & Act - Call LLM
        state = call_llm(state)

        # Check if LLM wants to use a tool
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            # Execute tool
            state = execute_tool_call(state)
            # Continue loop to observe result and plan again
            continue
        else:
            # No tool call - we're done
            print("\n" + "=" * 60)
            print("Final Response:")
            print("=" * 60)
            if hasattr(last_message, "content"):
                print(last_message.content)
            break

    print("\n" + "=" * 60)
    print(f"Agent finished after {state['step_count']} steps")
    print("=" * 60)


if __name__ == "__main__":
    main()
