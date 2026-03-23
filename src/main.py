"""CLI entry point for the LangGraph research agent."""
import sys
import argparse

# Set UTF-8 encoding for Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from src.graph import graph

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph Research Agent")
    parser.add_argument("topic", nargs="?", default=None, help="Research topic")
    args = parser.parse_args()

    topic = args.topic if args.topic else input("请输入研究主题: ")

    initial_state = {
        "topic": topic,
        "messages": [],
        "research_steps": [],
        "sources": [],
        "report_draft": "",
        "final_markdown_path": "",
    }

    result = graph.invoke(initial_state)
    print("\nReport saved to:", result.get("final_markdown_path", "unknown"))
