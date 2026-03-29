"""Daily evaluation runner for the research agent."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from evals.metrics.llm_judge import evaluate_all_metrics, evaluate_citation_quality

# Load environment
from dotenv import load_dotenv
load_dotenv('config.env')


def load_topics(dataset_path: str = None) -> List[Dict[str, Any]]:
    """Load test topics from JSON dataset."""
    if dataset_path is None:
        dataset_path = project_root / "evals" / "datasets" / "topics.json"

    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_agent_for_topic(topic: str, model: str = None) -> Dict[str, Any]:
    """Run the research agent for a single topic.

    Args:
        topic: The research topic
        model: Optional model override

    Returns:
        Dict with 'topic', 'answer', 'sources', 'report_path'
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from src.state import ResearchState
    from src.nodes import planner_node, researcher_node, writer_node, saver_node

    # Create evaluation graph without interrupts for automated evaluation
    eval_workflow = StateGraph(ResearchState)

    eval_workflow.add_node("planner", planner_node)
    eval_workflow.add_node("researcher", researcher_node)
    eval_workflow.add_node("writer", writer_node)
    eval_workflow.add_node("saver", saver_node)

    eval_workflow.add_edge(START, "planner")
    eval_workflow.add_edge("planner", "researcher")
    eval_workflow.add_edge("researcher", "writer")
    eval_workflow.add_edge("writer", "saver")
    eval_workflow.add_edge("saver", END)

    checkpointer = MemorySaver()
    compiled = eval_workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=[]  # No interrupts for evaluation
    )

    # Initial state
    initial_state = {
        "topic": topic,
        "messages": [],
        "research_steps": [],
        "sources": [],
        "report_draft": "",
        "final_markdown_path": "",
        "user_feedback": "auto"  # Auto-approve for evaluation
    }

    try:
        # Run the graph
        config = {"configurable": {"thread_id": f"eval_{datetime.now().timestamp()}"}}
        result = compiled.invoke(initial_state, config)

        return {
            "topic": topic,
            "answer": result.get("report_draft", ""),
            "sources": result.get("sources", []),
            "report_path": result.get("final_markdown_path", ""),
            "success": True,
            "error": None
        }
    except Exception as e:
        print(f"Error running agent for topic '{topic}': {e}")
        return {
            "topic": topic,
            "answer": "",
            "sources": [],
            "report_path": "",
            "success": False,
            "error": str(e)
        }


def run_evaluation(topics: List[Dict[str, Any]] = None, limit: int = None) -> Dict[str, Any]:
    """Run evaluation on all or limited topics.

    Args:
        topics: List of topic dicts with 'topic', 'golden_answer', 'key_points'
        limit: Optional limit on number of topics to evaluate

    Returns:
        Evaluation results dict
    """
    if topics is None:
        topics = load_topics()

    if limit:
        topics = topics[:limit]

    print(f"Starting evaluation on {len(topics)} topics...")

    results = []
    for i, topic_data in enumerate(topics):
        topic = topic_data.get("topic", "")
        print(f"[{i+1}/{len(topics)}] Evaluating: {topic}")

        # Run agent
        agent_result = run_agent_for_topic(topic)

        # Build result with golden answer for comparison
        result = {
            "topic": topic,
            "answer": agent_result.get("answer", ""),
            "sources": agent_result.get("sources", []),
            "report_path": agent_result.get("report_path", ""),
            "success": agent_result.get("success", False),
            "error": agent_result.get("error"),
            "golden_answer": topic_data.get("golden_answer", ""),
            "key_points": topic_data.get("key_points", [])
        }
        results.append(result)

        print(f"  - Success: {result['success']}, Sources: {len(result['sources'])}")

    return results


def _evaluate_single_topic_metrics(
    answer: str,
    sources: list,
    topic: str,
    golden_answer: str,
    key_points: list
) -> Dict[str, Any]:
    """Evaluate metrics for a single topic (runs in thread for timeout control)."""
    scores = evaluate_all_metrics(
        answer=answer,
        sources=sources,
        topic=topic,
        golden_answer=golden_answer,
        key_points=key_points
    )
    citation = evaluate_citation_quality(answer, sources)
    diversity = min(len(sources) / 10, 1.0) if sources else 0.0
    return {"scores": scores, "citation": citation, "diversity": diversity}


def calculate_metrics(results: List[Dict[str, Any]], per_topic_timeout: int = 180) -> Dict[str, Any]:
    """Calculate all evaluation metrics using combined LLM calls.

    Args:
        results: List of result dicts
        per_topic_timeout: Timeout in seconds for each topic's LLM evaluation (default: 180s)

    Returns:
        Metrics dict
    """
    print("\nCalculating metrics...")

    faithfulness_scores = []
    relevance_scores = []
    coverage_scores = []
    source_accuracy_scores = []
    source_coverage_scores = []
    diversity_scores = []
    citation_scores = []

    for i, r in enumerate(results):
        topic = r.get("topic", "")
        answer = r.get("answer", "")
        sources = r.get("sources", [])
        golden_answer = r.get("golden_answer", "")
        key_points = r.get("key_points", [])

        print(f"  [{i+1}/{len(results)}] Evaluating metrics: {topic}")

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    _evaluate_single_topic_metrics,
                    answer, sources, topic, golden_answer, key_points
                )
                eval_result = future.result(timeout=per_topic_timeout)

            scores = eval_result["scores"]
            faithfulness_scores.append(scores["faithfulness"])
            relevance_scores.append(scores["relevance"])
            source_accuracy_scores.append(scores["source_accuracy"])
            coverage_scores.append(scores["coverage"])
            citation_scores.append(eval_result["citation"])
            diversity_scores.append(eval_result["diversity"])
        except FuturesTimeoutError:
            print(f"    TIMEOUT: Metrics evaluation for '{topic}' exceeded {per_topic_timeout}s, using defaults")
            faithfulness_scores.append(0.5)
            relevance_scores.append(0.5)
            source_accuracy_scores.append(0.5)
            coverage_scores.append(0.5)
            citation_scores.append(0.0)
            diversity_scores.append(0.0)
        except Exception as e:
            print(f"    ERROR: Metrics evaluation for '{topic}' failed: {e}, using defaults")
            faithfulness_scores.append(0.5)
            relevance_scores.append(0.5)
            source_accuracy_scores.append(0.5)
            coverage_scores.append(0.5)
            citation_scores.append(0.0)
            diversity_scores.append(0.0)

    return {
        "faithfulness": {
            "scores": faithfulness_scores,
            "average": sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0
        },
        "relevance": {
            "relevance_scores": relevance_scores,
            "coverage_scores": coverage_scores,
            "average_relevance": sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0,
            "average_coverage": sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
        },
        "source_accuracy": {
            "accuracy_scores": source_accuracy_scores,
            "coverage_scores": coverage_scores,
            "diversity_scores": diversity_scores,
            "citation_scores": citation_scores,
            "average_accuracy": sum(source_accuracy_scores) / len(source_accuracy_scores) if source_accuracy_scores else 0.0,
            "average_coverage": sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0,
            "average_diversity": sum(diversity_scores) / len(diversity_scores) if diversity_scores else 0.0,
            "average_citation": sum(citation_scores) / len(citation_scores) if citation_scores else 0.0
        }
    }


def generate_report(
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    timestamp: str = None
) -> Dict[str, Any]:
    """Generate evaluation report.

    Args:
        results: List of result dicts
        metrics: Metrics dict
        timestamp: Optional timestamp string

    Returns:
        Report dict
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Calculate overall score
    overall = (
        metrics["faithfulness"]["average"] * 0.35 +
        metrics["relevance"]["average_relevance"] * 0.35 +
        metrics["source_accuracy"]["average_accuracy"] * 0.30
    )

    report = {
        "timestamp": datetime.now().isoformat(),
        "topic_count": len(results),
        "success_count": sum(1 for r in results if r.get("success", False)),
        "overall_score": round(overall, 4),
        "metrics": {
            "faithfulness": {
                "average": round(metrics["faithfulness"]["average"], 4),
                "scores": [round(s, 4) for s in metrics["faithfulness"]["scores"]]
            },
            "relevance": {
                "average": round(metrics["relevance"]["average_relevance"], 4),
                "coverage_average": round(metrics["relevance"]["average_coverage"], 4),
                "scores": [round(s, 4) for s in metrics["relevance"]["relevance_scores"]]
            },
            "source_accuracy": {
                "average": round(metrics["source_accuracy"]["average_accuracy"], 4),
                "coverage_average": round(metrics["source_accuracy"]["average_coverage"], 4),
                "diversity_average": round(metrics["source_accuracy"]["average_diversity"], 4),
                "citation_average": round(metrics["source_accuracy"]["average_citation"], 4)
            }
        },
        "results": [
            {
                "topic": r["topic"],
                "success": r.get("success", False),
                "faithfulness_score": r.get("faithfulness_score", None),
                "relevance_score": r.get("relevance_score", None),
                "source_accuracy_score": r.get("source_accuracy_score", None)
            }
            for r in results
        ]
    }

    return report


def save_report(report: Dict[str, Any], output_dir: str = None) -> str:
    """Save evaluation report to JSON file.

    Args:
        report: Report dict
        output_dir: Output directory

    Returns:
        Path to saved report
    """
    if output_dir is None:
        output_dir = project_root / "evals" / "reports"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"daily_eval_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return str(filepath)


def print_summary(report: Dict[str, Any]) -> None:
    """Print evaluation summary to console."""
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Topics evaluated: {report['topic_count']}")
    print(f"Success rate: {report['success_count']}/{report['topic_count']}")
    print(f"Overall score: {report['overall_score']:.4f}")
    print("\nMetric averages:")
    print(f"  - Faithfulness:     {report['metrics']['faithfulness']['average']:.4f}")
    print(f"  - Relevance:        {report['metrics']['relevance']['average']:.4f}")
    print(f"  - Source Accuracy:   {report['metrics']['source_accuracy']['average']:.4f}")
    print("=" * 60)


def main():
    """Main entry point for daily evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Run daily evaluation on research agent")
    parser.add_argument("--limit", "-n", type=int, default=None,
                        help="Limit number of topics to evaluate")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Output directory for report")
    parser.add_argument("--dataset", "-d", type=str, default=None,
                        help="Path to topics dataset JSON")

    args = parser.parse_args()

    # Load topics
    topics = load_topics(args.dataset)
    print(f"Loaded {len(topics)} topics from dataset")

    # Run evaluation
    results = run_evaluation(topics, limit=args.limit)

    # Calculate metrics
    metrics = calculate_metrics(results)

    # Add per-result scores to results
    for i, result in enumerate(results):
        if i < len(metrics["faithfulness"]["scores"]):
            result["faithfulness_score"] = metrics["faithfulness"]["scores"][i]
        if i < len(metrics["relevance"]["relevance_scores"]):
            result["relevance_score"] = metrics["relevance"]["relevance_scores"][i]
        if i < len(metrics["source_accuracy"]["accuracy_scores"]):
            result["source_accuracy_score"] = metrics["source_accuracy"]["accuracy_scores"][i]

    # Generate report
    report = generate_report(results, metrics)

    # Save report
    report_path = save_report(report, args.output_dir)
    print(f"\nReport saved to: {report_path}")

    # Print summary
    print_summary(report)

    return report


if __name__ == "__main__":
    main()
