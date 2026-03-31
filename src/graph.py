"""LangGraph workflow for the research agent."""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import ResearchState
from src.nodes import planner_node, researcher_node, writer_node, saver_node


def build_graph(interrupt_before=None):
    """Build and compile the research agent graph.

    Args:
        interrupt_before: List of node names to interrupt before.
            Defaults to ["researcher", "saver"] for human-in-the-loop.
            Pass [] for automated evaluation.

    Returns:
        Compiled StateGraph with MemorySaver checkpointer.
    """
    if interrupt_before is None:
        interrupt_before = ["researcher", "saver"]

    workflow = StateGraph(ResearchState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("saver", saver_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("writer", "saver")
    workflow.add_edge("saver", END)

    checkpointer = MemorySaver()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before
    )


# Default graph for interactive use (with human-in-the-loop interrupts)
graph = build_graph()
