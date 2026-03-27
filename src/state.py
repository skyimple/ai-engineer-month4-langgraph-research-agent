"""LangGraph state definitions for the research agent."""

from typing import Annotated, List, TypedDict

from langgraph.graph import add_messages


class ResearchState(TypedDict):
    """State for the research agent workflow."""

    topic: str
    messages: Annotated[List, add_messages]
    research_steps: List[str]
    sources: List[dict]
    report_draft: str
    final_markdown_path: str
    user_feedback: str = ""
    error_message: str = ""
