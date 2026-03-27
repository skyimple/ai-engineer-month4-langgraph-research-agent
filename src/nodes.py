"""Intelligent nodes for the Research Agent."""
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage

from src.config import llm, get_llm, traceable
from src.tools import search_tool
from src.guardrails.rails import check_output_guardrails


import sys

# BadRequestError for handling DashScope content filter errors
try:
    from openai import BadRequestError
except ImportError:
    BadRequestError = None


def is_content_filter_error(error: Exception) -> bool:
    """Check if the error is a DashScope content filter rejection.

    Args:
        error: The exception to check

    Returns:
        True if this is a content filter error, False otherwise
    """
    if BadRequestError is None:
        return False

    if not isinstance(error, BadRequestError):
        return False

    error_str = str(error).lower()
    # DashScope content filter errors typically contain these indicators
    content_filter_indicators = [
        "data_inspection_failed",
        "content filter",
        "content_filter",
        "inappropriate content",
        "sensitive content",
    ]
    return any(indicator in error_str for indicator in content_filter_indicators)

def clean_string(s: str) -> str:
    """Remove surrogate characters that cause encoding issues."""
    return s.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')


def clean_state_strings(state: dict) -> dict:
    """Clean all string values in state of surrogate characters."""
    cleaned = {}
    for key, value in state.items():
        if isinstance(value, str):
            cleaned[key] = clean_string(value)
        elif isinstance(value, list):
            cleaned[key] = [
                clean_string(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


@traceable(metadata={"version": "1.0", "node": "planner"})
def planner_node(state: dict, original_steps: list = None, llm=None) -> dict:
    """Plan the research approach by calling LLM with search tool.

    Args:
        state: Current research state with 'topic' and optional 'user_feedback'
        original_steps: Original research steps (when modifying)
        llm: Optional LLM instance for A/B testing

    Returns:
        Updated state with 'research_steps' list
    """
    # Clean state strings to remove surrogate characters
    state = clean_state_strings(state)

    topic = state["topic"]
    user_feedback = state.get("user_feedback", "")
    print(f"Planning research for: {topic}")

    # Build prompt with user feedback if present
    feedback_hint = ""
    original_steps_hint = ""
    if user_feedback and user_feedback.startswith("modify:"):
        feedback_hint = f"\n\n用户修改意见：{user_feedback[7:].strip()}\n请根据用户意见调整研究计划。"
        # Add original plan as reference when modifying
        if original_steps:
            original_steps_hint = f"\n\n原研究计划：\n" + "\n".join(f"- {s}" for s in original_steps)

    # System prompt for planner
    planner_prompt = f"""你是一个研究规划专家。请为以下主题制定3-5个研究步骤：

主题：{topic}{feedback_hint}{original_steps_hint}

请以JSON格式返回研究步骤列表，格式如下：
{{"research_steps": ["步骤1", "步骤2", "步骤3"]}}

每个步骤应该是一个具体的搜索查询或研究任务。"""

    # Call LLM directly (without bind_tools to get text response)
    actual_llm = llm or get_llm()
    try:
        response = actual_llm.invoke([
            HumanMessage(content=planner_prompt)
        ])
    except BadRequestError as e:
        if is_content_filter_error(e):
            error_msg = (
                "研究计划生成被内容安全过滤器拦截。\n"
                "可能原因：研究主题触及了API安全限制。\n\n"
                "建议：\n"
                "1. 尝试修改研究主题的表述\n"
                "2. 使用更宽泛或学术性的表述"
            )
            print(f"\n⚠️ 内容安全过滤器拦截: {error_msg}")
            # Return error state - user can retry with modified topic
            return {
                "research_steps": [],
                "error_message": f"CONTENT_FILTER_ERROR: {error_msg}"
            }
        else:
            raise

    # Parse response to get research steps
    research_steps = []
    if hasattr(response, "content") and response.content:
        try:
            # Try to extract JSON from response
            content = response.content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            parsed = json.loads(json_str.strip())
            research_steps = parsed.get("research_steps", [])
        except (json.JSONDecodeError, IndexError):
            # Fallback: split by newlines
            research_steps = [
                line.strip() for line in response.content.split("\n")
                if line.strip() and line.strip()[0].isdigit()
            ]

    # If still empty, keep original research_steps if modifying, otherwise use fallback
    if not research_steps:
        if user_feedback and original_steps:
            # When modifying, prefer to keep original steps if LLM fails
            research_steps = original_steps
            print(f"⚠️ 无法生成新计划，保留原计划")
        elif not user_feedback:
            research_steps = [f"{topic}的基本概念", f"{topic}的最新发展", f"{topic}的应用场景"]

    print(f"Generated {len(research_steps)} research steps")
    return {"research_steps": research_steps}


@traceable(metadata={"version": "1.0", "node": "researcher"})
def researcher_node(state: dict) -> dict:
    """Conduct research by executing search for each step.

    Args:
        state: Current state with 'research_steps'

    Returns:
        Updated state with 'messages' and 'sources'
    """
    # Clean state strings to remove surrogate characters
    state = clean_state_strings(state)

    research_steps = state.get("research_steps", [])
    print(f"Researching {len(research_steps)} steps...")

    messages = list(state.get("messages", []))
    sources = list(state.get("sources", []))

    for i, step in enumerate(research_steps):
        print(f"  [{i+1}/{len(research_steps)}] Searching: {step}", flush=True)

        # Execute search tool
        result = search_tool.invoke(step)

        # Add to messages
        messages.append(HumanMessage(content=f"Research step: {step}"))
        messages.append(AIMessage(content=result))

        # Extract source info from result
        lines = result.split("\n")
        for line in lines:
            if line.strip().startswith("- "):
                # Parse "- Title: URL" format
                parts = line[2:].split(": ", 1)
                if len(parts) >= 1:
                    title = parts[0].strip()
                    url = parts[1].split("\n")[0].strip() if len(parts) > 1 else ""
                    snippet = line.split("\n  ")[1] if "\n  " in line else ""

                    # Avoid duplicates
                    source_entry = {"title": title, "url": url, "snippet": snippet}
                    if source_entry not in sources:
                        sources.append(source_entry)

    print(f"Collected {len(sources)} unique sources", flush=True)

    # Check output guardrails before returning
    if messages:
        is_safe, safety_msg = check_output_guardrails(messages[-1].content)
        if not is_safe:
            raise ValueError(safety_msg)

    return {"messages": messages, "sources": sources}


@traceable(metadata={"version": "1.0", "node": "writer"})
def writer_node(state: dict, llm=None) -> dict:
    """Write the research report using collected information.

    Args:
        state: Current state with 'messages', 'sources', 'research_steps', and optional 'user_feedback'
        llm: Optional LLM instance for A/B testing

    Returns:
        Updated state with 'report_draft'
    """
    # Clean state strings to remove surrogate characters
    state = clean_state_strings(state)

    topic = state["topic"]
    messages = state.get("messages", [])
    sources = state.get("sources", [])
    user_feedback = state.get("user_feedback", "")
    research_steps = state.get("research_steps", [])

    print(f"Writing report on: {topic}")

    # Add user feedback hint if present
    feedback_hint = ""
    if user_feedback and user_feedback.startswith("modify:"):
        feedback_hint = f"\n\n用户修改意见：{user_feedback[7:].strip()}\n请根据用户意见重新撰写报告。"

    # Format research steps for the prompt
    steps_text = ""
    if research_steps:
        steps_text = "## 研究计划（请按此结构撰写报告各章节）\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(research_steps))

    # Format sources for the prompt
    sources_text = ""
    for i, s in enumerate(sources, 1):
        sources_text += f"{i}. **{s.get('title', 'Untitled')}**\n   URL: {s.get('url', 'N/A')}\n   {s.get('snippet', '')}\n\n"

    writer_prompt = f"""你是一个专业的研究报告撰写专家。请根据以下研究计划和研究资料撰写一份结构良好的Markdown研究报告。

主题：{topic}
{feedback_hint}

{steps_text}

## 研究资料
{sources_text if sources_text else "（暂无研究资料，请基于主题撰写基本信息）"}

## 报告要求
1. 标题（# 标题格式）
2. 摘要（Abstract）- 简要概述主题
3. 正文小节 - 按照上述研究计划的结构撰写，使用##格式
4. 来源列表 - 列出所有参考来源

## 输出格式
请直接输出Markdown格式的研究报告，不要添加额外的解释。"""

    # Call LLM to generate report
    actual_llm = llm or get_llm()
    try:
        response = actual_llm.invoke([
            HumanMessage(content=writer_prompt)
        ])
    except BadRequestError as e:
        if is_content_filter_error(e):
            error_msg = (
                "报告生成被内容安全过滤器拦截。\n"
                "可能原因：研究主题或生成内容触及了API安全限制。\n\n"
                "建议：\n"
                "1. 尝试修改研究主题的表述\n"
                "2. 使用 'modify: <修改指令>' 提供更具体的撰写方向\n"
                "3. 尝试缩短或简化研究范围"
            )
            print(f"\n⚠️ 内容安全过滤器拦截: {error_msg}")
            # Return error state with empty report_draft and error message
            return {
                "report_draft": "",
                "error_message": f"CONTENT_FILTER_ERROR: {error_msg}"
            }
        else:
            # Re-raise for other BadRequestError types
            raise

    report_draft = response.content if hasattr(response, "content") else str(response)

    # Check output guardrails before returning
    is_safe, safety_msg = check_output_guardrails(report_draft)
    if not is_safe:
        raise ValueError(safety_msg)

    print(f"Report written ({len(report_draft)} chars)")
    return {"report_draft": report_draft}


@traceable(metadata={"version": "1.0", "node": "saver"})
def saver_node(state: dict) -> dict:
    """Save the report to a markdown file.

    Args:
        state: Current state with 'report_draft'

    Returns:
        Updated state with 'final_markdown_path'
    """
    from src.tools import save_markdown_tool

    report_draft = state.get("report_draft", "")
    topic = state.get("topic", "research_report")

    # Generate filename from topic
    filename = f"{topic[:30].replace(' ', '_')}_report.md"

    print(f"Saving report to outputs/{filename}")

    # Save the report
    result = save_markdown_tool.invoke({
        "content": report_draft,
        "filename": filename
    })

    print(f"Saved: {result}")
    return {"final_markdown_path": result}
