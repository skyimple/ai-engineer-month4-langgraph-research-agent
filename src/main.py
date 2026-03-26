"""CLI entry point for the LangGraph research agent with human-in-the-loop."""
import sys
import io
import argparse
from langgraph.types import Command

# Set UTF-8 encoding for Windows stdout
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Set UTF-8 encoding for Windows stdin (for piped input with Chinese)
if sys.platform == 'win32':
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

from src.graph import graph
from src.nodes import planner_node, researcher_node, writer_node, saver_node
from src.guardrails.rails import check_input_guardrails


def get_topic_from_args():
    parser = argparse.ArgumentParser(description="LangGraph Research Agent")
    parser.add_argument("topic", nargs="?", default=None, help="Research topic")
    args = parser.parse_args()
    return args.topic if args.topic else input("请输入研究主题: ")


def handle_planner_interrupt(state):
    """Handle interrupt after planner node - show research steps and get user feedback."""
    print("\n" + "="*60)
    print("📋 研究计划已生成:")
    print("="*60)
    for i, step in enumerate(state.get("research_steps", []), 1):
        print(f"  {i}. {step}")
    print("="*60)

    while True:
        try:
            user_input = input("\n输入 'approve' 继续，或 'modify: <修改指令>' 修改计划: ").strip()
            if user_input.lower() == "approve":
                return "approve"
            elif user_input.lower().startswith("modify:"):
                instruction = user_input[7:].strip()
                return f"modify: {instruction}"
            else:
                print("无效输入，请输入 'approve' 或 'modify: <修改指令>'")
        except (KeyboardInterrupt, EOFError):
            print("\n\n操作已取消。")
            sys.exit(0)


def handle_writer_interrupt(state):
    """Handle interrupt after writer node - show report draft and get user feedback."""
    print("\n" + "="*60)
    print("📄 报告草稿:")
    print("="*60)
    print(state.get("report_draft", ""))
    print("="*60)

    while True:
        try:
            user_input = input("\n输入 'approve' 保存，或 'modify: <修改指令>' 修改报告: ").strip()
            if user_input.lower() == "approve":
                return "approve"
            elif user_input.lower().startswith("modify:"):
                instruction = user_input[7:].strip()
                return f"modify: {instruction}"
            else:
                print("无效输入，请输入 'approve' 或 'modify: <修改指令>'")
        except (KeyboardInterrupt, EOFError):
            print("\n\n操作已取消。")
            sys.exit(0)


def run_research(topic: str):
    """Run the research agent with human-in-the-loop."""
    # Check input with Guardrails
    is_safe, safety_message = check_input_guardrails(topic)
    if not is_safe:
        print(safety_message)
        return None

    thread_id = f"research_{topic}_{id(topic)}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "topic": topic,
        "messages": [],
        "research_steps": [],
        "sources": [],
        "report_draft": "",
        "final_markdown_path": "",
        "user_feedback": "",
    }

    print(f"\n🔍 开始研究主题: {topic}")

    # Run until first interrupt (after planner)
    result = graph.invoke(initial_state, config=config)

    # Handle planner interrupt - loop until approved
    while True:
        if result.get("research_steps"):
            feedback = handle_planner_interrupt(result)
            if feedback == "approve":
                # Continue to researcher
                result = graph.invoke(Command(resume="continue"), config=config)
                break
            else:
                # modify - re-run planner, researcher, writer completely manually
                print(f"\n🔄 重新规划: {feedback}")
                # Preserve original research_steps for fallback
                original_steps = result.get("research_steps", [])
                new_state = {
                    **result,
                    "user_feedback": feedback,
                    "research_steps": [],
                    "messages": [],
                }
                # Call planner directly to get new research_steps
                planner_result = planner_node(new_state, original_steps=original_steps)
                # Use new steps if generated, otherwise keep original
                if planner_result.get("research_steps"):
                    result.update(planner_result)
                else:
                    print("⚠️  无法生成新计划，保留原计划")
                result["user_feedback"] = ""

                # Display the new plan
                print("\n" + "="*60)
                print("📋 新研究计划:")
                print("="*60)
                for i, step in enumerate(result.get("research_steps", []), 1):
                    print(f"  {i}. {step}")
                print("="*60)

                # Manually call researcher with the NEW research_steps
                print("\n🔍 使用新计划进行搜索...")
                researcher_result = researcher_node(result)
                result.update(researcher_result)

                # Manually call writer
                print("\n✍️  生成报告...")
                writer_result = writer_node(result)
                result.update(writer_result)
                # result now has report_draft, break to writer interrupt loop
                break
        else:
            break

    # Handle writer interrupt - loop until approved
    while True:
        if result.get("report_draft"):
            feedback = handle_writer_interrupt(result)
            if feedback == "approve":
                # Save manually and exit
                print("\n💾 保存报告...")
                topic_for_filename = result.get("topic", "report")
                filename = f"{topic_for_filename[:30].replace(' ', '_')}_report.md"
                saver_result = saver_node({**result, "report_draft": result["report_draft"]})
                result.update(saver_result)
                break
            else:
                # modify - re-run writer with feedback
                print(f"\n🔄 重新撰写: {feedback}")
                new_state = {
                    **result,
                    "user_feedback": feedback,
                }
                # Call writer directly with feedback
                writer_result = writer_node(new_state)
                result = {**result, **writer_result, "user_feedback": ""}
                # Loop back to show new draft and prompt again
        else:
            break

    print("\n" + "="*60)
    print(f"✅ 报告已保存到: {result.get('final_markdown_path', 'unknown')}")
    print("="*60)

    return result


if __name__ == "__main__":
    topic = get_topic_from_args()
    try:
        run_research(topic)
    except KeyboardInterrupt:
        print("\n\n研究已取消。")
        sys.exit(0)
