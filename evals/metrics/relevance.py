"""Relevance metric: Evaluates how relevant the answer is to the research topic."""

from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv('config.env')


def evaluate_relevance(answer: str, topic: str, golden_answer: str = None) -> float:
    """Evaluate relevance score (0-1) of the answer to the topic.

    Args:
        answer: The generated answer/report
        topic: The research topic
        golden_answer: Optional golden standard answer for comparison

    Returns:
        Relevance score between 0 and 1
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return 0.5  # Default fallback

    llm = ChatOpenAI(
        model="qwen3.5-plus",
        temperature=0.0,
        max_tokens=500,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    prompt = f"""你是一个评估专家。请评估以下答案与研究主题的相关程度。

研究主题: {topic}

答案:
{answer[:2000]}  # Limit answer length for prompt

请从以下维度评估相关性：
1. 答案是否紧扣主题
2. 答案是否覆盖了主题的核心方面
3. 答案是否存在偏题或无关内容

请给出0-1之间的分数，0表示完全不相关，1表示完全相关。
只需输出一个数字，保留2位小数，例如：0.85
"""

    try:
        response = llm.invoke(prompt)
        score_text = response.content.strip()
        # Extract number from response
        import re
        match = re.search(r'0?\.\d+', score_text)
        if match:
            return float(match.group())
        return 0.5
    except Exception as e:
        print(f"Relevance evaluation error: {e}")
        return 0.5


def evaluate_relevance_with_golden(
    answer: str,
    topic: str,
    golden_answer: str,
    key_points: List[str]
) -> Dict[str, float]:
    """Evaluate relevance by comparing with golden answer and key points.

    Args:
        answer: The generated answer
        topic: The research topic
        golden_answer: Golden standard answer
        key_points: List of key evaluation points

    Returns:
        Dict with 'relevance_score' and 'coverage_score'
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return {"relevance_score": 0.5, "coverage_score": 0.5}

    llm = ChatOpenAI(
        model="qwen3.5-plus",
        temperature=0.0,
        max_tokens=500,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    key_points_str = "\n".join([f"- {kp}" for kp in key_points])

    prompt = f"""你是一个评估专家。请评估答案与研究主题的相关性。

研究主题: {topic}

关键评估点:
{key_points_str}

标准答案:
{golden_answer[:1000]}

待评估答案:
{answer[:2000]}

请分别给出：
1. 相关性分数(0-1)：答案是否紧扣主题
2. 覆盖率分数(0-1)：答案覆盖了多少关键评估点

输出格式：
relevance: 0.XX
coverage: 0.XX
"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()

        import re
        rel_match = re.search(r'relevance:\s*0?\.\d+', content, re.IGNORECASE)
        cov_match = re.search(r'coverage:\s*0?\.\d+', content, re.IGNORECASE)

        relevance = 0.5
        coverage = 0.5

        if rel_match:
            num_match = re.search(r'0?\.\d+', rel_match.group())
            if num_match:
                relevance = float(num_match.group())

        if cov_match:
            num_match = re.search(r'0?\.\d+', cov_match.group())
            if num_match:
                coverage = float(num_match.group())

        return {
            "relevance_score": relevance,
            "coverage_score": coverage
        }
    except Exception as e:
        print(f"Relevance evaluation error: {e}")
        return {"relevance_score": 0.5, "coverage_score": 0.5}


def batch_evaluate_relevance(
    results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Evaluate relevance for multiple results.

    Args:
        results: List of dicts with 'topic', 'answer', and optionally 'golden_answer', 'key_points'

    Returns:
        Dict with 'relevance_scores', 'coverage_scores', 'average_relevance', 'average_coverage'
    """
    relevance_scores = []
    coverage_scores = []

    for result in results:
        if result.get("golden_answer") and result.get("key_points"):
            scores = evaluate_relevance_with_golden(
                answer=result.get("answer", ""),
                topic=result.get("topic", ""),
                golden_answer=result.get("golden_answer", ""),
                key_points=result.get("key_points", [])
            )
            relevance_scores.append(scores["relevance_score"])
            coverage_scores.append(scores["coverage_score"])
        else:
            score = evaluate_relevance(
                answer=result.get("answer", ""),
                topic=result.get("topic", "")
            )
            relevance_scores.append(score)

    return {
        "relevance_scores": relevance_scores,
        "coverage_scores": coverage_scores if coverage_scores else [0.0] * len(relevance_scores),
        "average_relevance": sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0,
        "average_coverage": sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    }
