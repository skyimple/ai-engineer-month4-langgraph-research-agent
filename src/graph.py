"""LangGraph workflow for the research agent."""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import ResearchState
from src.nodes import planner_node, researcher_node, writer_node, saver_node

# Phoenix callback（可选）- 通过环境变量启用
PHOENIX_CALLBACK = None
try:
    import phoenix as px
    if px is not None:
        # Phoenix 配置通过环境变量自动生效
        PHOENIX_CALLBACK_AVAILABLE = True
except ImportError:
    PHOENIX_CALLBACK_AVAILABLE = False

# Build the linear workflow graph
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
graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["researcher", "saver"]
)
