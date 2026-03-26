"""A/B Testing Framework for the Research Agent.

This module runs comparative experiments between two versions (A and B) of the research agent,
measuring latency, token consumption, and output quality.

Usage:
    python ab_test.py "AI"
"""
import os
import sys
import io
import time
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

# Set UTF-8 encoding for Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.platform == 'win32':
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

# Load environment variables
from dotenv import load_dotenv
load_dotenv('config.env')

from src.config import get_llm_for_ab_version, AB_TEST_MODEL_A, AB_TEST_MODEL_B
from src.nodes import planner_node, researcher_node, writer_node


class ABTestResult:
    """Container for A/B test results."""

    def __init__(self, version: str):
        self.version = version
        self.start_time: float = 0
        self.end_time: float = 0
        self.latency_seconds: float = 0
        self.token_usage: Dict[str, int] = {}
        self.output_quality: Optional[float] = None
        self.research_steps: list = []
        self.sources_count: int = 0
        self.report_length: int = 0
        self.report_content: str = ""
        self.error: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.token_usage.get('total_tokens', 0)

    @property
    def prompt_tokens(self) -> int:
        return self.token_usage.get('prompt_tokens', 0)

    @property
    def completion_tokens(self) -> int:
        return self.token_usage.get('completion_tokens', 0)


def run_version(version: str, topic: str) -> ABTestResult:
    """Run the research agent for a specific version (A or B).

    Args:
        version: The A/B version to run ('A' or 'B')
        topic: The research topic

    Returns:
        ABTestResult object with metrics
    """
    result = ABTestResult(version)
    result.start_time = time.time()

    try:
        # Get the appropriate LLM for this version
        llm = get_llm_for_ab_version(version)

        # Track token usage via callback
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        def track_tokens(response):
            """Track token usage from LLM response."""
            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                token_usage['prompt_tokens'] = getattr(usage, 'prompt_tokens', 0)
                token_usage['completion_tokens'] = getattr(usage, 'completion_tokens', 0)
                token_usage['total_tokens'] = getattr(usage, 'total_tokens', 0)
            return response

        # Prepare initial state
        initial_state = {
            "topic": topic,
            "messages": [],
            "research_steps": [],
            "sources": [],
            "report_draft": "",
            "final_markdown_path": "",
            "user_feedback": "",
        }

        print(f"\n{'='*60}")
        print(f"Running Version {version} (Model: {AB_TEST_MODEL_B if version == 'B' else AB_TEST_MODEL_A})")
        print(f"{'='*60}")

        # Step 1: Planner
        print(f"\n[Version {version}] Step 1/3: Planning...")
        planner_result = planner_node(initial_state, llm=llm)
        result.research_steps = planner_result.get("research_steps", [])
        print(f"[Version {version}] Generated {len(result.research_steps)} research steps")

        # Update state for researcher
        state_after_planner = {**initial_state, **planner_result}

        # Step 2: Researcher
        print(f"\n[Version {version}] Step 2/3: Researching...")
        researcher_result = researcher_node(state_after_planner)
        result.sources_count = len(researcher_result.get("sources", []))
        print(f"[Version {version}] Collected {result.sources_count} sources")

        # Update state for writer
        state_after_researcher = {**state_after_planner, **researcher_result}

        # Step 3: Writer
        print(f"\n[Version {version}] Step 3/3: Writing report...")
        writer_result = writer_node(state_after_researcher, llm=llm)
        result.report_content = writer_result.get("report_draft", "")
        result.report_length = len(result.report_content)
        print(f"[Version {version}] Report written ({result.report_length} chars)")

        # Get final token usage
        result.token_usage = token_usage

        result.end_time = time.time()
        result.latency_seconds = result.end_time - result.start_time

    except Exception as e:
        result.error = str(e)
        result.end_time = time.time()
        result.latency_seconds = result.end_time - result.start_time
        print(f"[Version {version}] Error: {e}")

    return result


def evaluate_quality(report_a: str, report_b: str, topic: str) -> Dict[str, float]:
    """Evaluate relative quality between two reports.

    This uses a simple heuristic based on report structure and length.
    A more sophisticated implementation would use LLM-based evaluation.

    Args:
        report_a: Report from version A
        report_b: Report from version B
        topic: Research topic

    Returns:
        Dict with quality scores for each version
    """
    def calculate_quality_score(report: str) -> float:
        """Calculate a quality score based on report characteristics."""
        if not report:
            return 0.0

        score = 0.0

        # Length score (normalized, max 30 points)
        length = len(report)
        score += min(30, length / 100)

        # Structure score (headers, sections)
        header_count = report.count('#')
        score += min(20, header_count * 2)

        # Has abstract
        if 'abstract' in report.lower():
            score += 10

        # Has sources/references
        if '来源' in report or 'reference' in report.lower() or 'sources' in report.lower():
            score += 10

        # Has conclusion
        if '结论' in report or 'conclusion' in report.lower():
            score += 10

        # Token efficiency (quality per token)
        word_count = len(report.split())
        if word_count > 0:
            score += min(20, word_count / 50)

        return min(100, score)

    score_a = calculate_quality_score(report_a)
    score_b = calculate_quality_score(report_b)

    return {"A": score_a, "B": score_b}


def generate_comparison_report(
    topic: str,
    result_a: ABTestResult,
    result_b: ABTestResult,
    quality_scores: Dict[str, float]
) -> str:
    """Generate a markdown comparison report for the A/B test.

    Args:
        topic: Research topic
        result_a: Results from version A
        result_b: Results from version B
        quality_scores: Quality scores for each version

    Returns:
        Markdown string with the comparison report
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate differences
    latency_diff = result_b.latency_seconds - result_a.latency_seconds
    latency_diff_pct = (latency_diff / result_a.latency_seconds * 100) if result_a.latency_seconds > 0 else 0

    token_diff = result_b.total_tokens - result_a.total_tokens
    token_diff_pct = (token_diff / result_a.total_tokens * 100) if result_a.total_tokens > 0 else 0

    quality_diff = quality_scores["B"] - quality_scores["A"]

    report = f"""# A/B Test Comparison Report

## Test Information

- **Topic**: {topic}
- **Timestamp**: {timestamp}
- **Version A Model**: {AB_TEST_MODEL_A}
- **Version B Model**: {AB_TEST_MODEL_B}

---

## Performance Metrics

### Latency

| Metric | Version A | Version B | Difference |
|--------|-----------|-----------|------------|
| Total Time (s) | {result_a.latency_seconds:.2f} | {result_b.latency_seconds:.2f} | {latency_diff:+.2f} ({latency_diff_pct:+.1f}%) |

### Token Consumption

| Metric | Version A | Version B | Difference |
|--------|-----------|-----------|------------|
| Prompt Tokens | {result_a.prompt_tokens} | {result_b.prompt_tokens} | {result_b.prompt_tokens - result_a.prompt_tokens:+d} |
| Completion Tokens | {result_a.completion_tokens} | {result_b.completion_tokens} | {result_b.completion_tokens - result_a.completion_tokens:+d} |
| Total Tokens | {result_a.total_tokens} | {result_b.total_tokens} | {token_diff:+d} ({token_diff_pct:+.1f}%) |

### Output Quality

| Metric | Version A | Version B | Difference |
|--------|-----------|-----------|------------|
| Quality Score | {quality_scores["A"]:.1f} | {quality_scores["B"]:.1f} | {quality_diff:+.1f} |

---

## Research Steps

### Version A
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(result_a.research_steps)) or "_No steps generated_"}

### Version B
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(result_b.research_steps)) or "_No steps generated_"}

---

## Output Summary

### Version A
- **Sources Collected**: {result_a.sources_count}
- **Report Length**: {result_a.report_length} characters
- **Errors**: {result_a.error or "None"}

### Version B
- **Sources Collected**: {result_b.sources_count}
- **Report Length**: {result_b.report_length} characters
- **Errors**: {result_b.error or "None"}

---

## Conclusion

{"**Version B** outperforms Version A" if quality_diff > 5 and latency_diff < 0 else "**Version A** performs better overall" if quality_scores["A"] > quality_scores["B"] + 5 or latency_diff > 0 else "Results are comparable - further testing recommended"}

- **Latency Winner**: {"Version B" if latency_diff < 0 else "Version A" if latency_diff > 0 else "Tie"}
- **Token Efficiency Winner**: {"Version B" if token_diff < 0 else "Version A" if token_diff > 0 else "Tie"}
- **Quality Winner**: {"Version B" if quality_scores["B"] > quality_scores["A"] else "Version A" if quality_scores["A"] > quality_scores["B"] else "Tie"}

---

_Generated by A/B Testing Framework_
"""

    return report


def save_report(content: str, filename: str) -> str:
    """Save a report to the evals/reports directory.

    Args:
        content: Report content
        filename: Output filename

    Returns:
        Full path to saved file
    """
    import os
    output_dir = "evals/reports"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def run_ab_test(topic: str) -> Dict[str, ABTestResult]:
    """Run the complete A/B test for a given topic.

    Args:
        topic: Research topic

    Returns:
        Dict with results for version A and B
    """
    print(f"\n{'#'*60}")
    print(f"# A/B Testing Framework")
    print(f"# Topic: {topic}")
    print(f"{'#'*60}")

    # Run Version A
    print("\n\n")
    result_a = run_version("A", topic)

    # Run Version B
    print("\n\n")
    result_b = run_version("B", topic)

    # Evaluate quality
    quality_scores = evaluate_quality(result_a.report_content, result_b.report_content, topic)
    result_a.output_quality = quality_scores["A"]
    result_b.output_quality = quality_scores["B"]

    # Generate comparison report
    comparison_report = generate_comparison_report(topic, result_a, result_b, quality_scores)

    # Save reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    topic_safe = topic.replace(" ", "_")[:20]

    report_path = save_report(comparison_report, f"ab_test_{topic_safe}_{timestamp}.md")
    print(f"\n\nComparison report saved to: {report_path}")

    # Save individual reports
    if result_a.report_content:
        save_report(result_a.report_content, f"ab_test_{topic_safe}_version_A.md")
        print(f"Version A report saved to: evals/reports/ab_test_{topic_safe}_version_A.md")

    if result_b.report_content:
        save_report(result_b.report_content, f"ab_test_{topic_safe}_version_B.md")
        print(f"Version B report saved to: evals/reports/ab_test_{topic_safe}_version_B.md")

    # Print summary
    print(f"\n\n{'='*60}")
    print("A/B Test Summary")
    print(f"{'='*60}")
    print(f"Version A: {result_a.latency_seconds:.2f}s, {result_a.total_tokens} tokens, quality: {quality_scores['A']:.1f}")
    print(f"Version B: {result_b.latency_seconds:.2f}s, {result_b.total_tokens} tokens, quality: {quality_scores['B']:.1f}")
    print(f"{'='*60}")

    return {"A": result_a, "B": result_b}


def main():
    """Main entry point for A/B testing."""
    parser = argparse.ArgumentParser(description="A/B Testing Framework for Research Agent")
    parser.add_argument("topic", nargs="?", default="AI", help="Research topic")
    args = parser.parse_args()

    topic = args.topic if args.topic else "AI"

    try:
        run_ab_test(topic)
    except KeyboardInterrupt:
        print("\n\nA/B test interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nA/B test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
