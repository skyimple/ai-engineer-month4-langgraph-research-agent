"""Source Accuracy metric: Evaluates the accuracy and quality of cited sources."""

from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv('config.env')


def evaluate_source_accuracy(sources: List[Dict[str, Any]], topic: str) -> float:
    """Evaluate source accuracy score (0-1) based on source quality and relevance.

    Args:
        sources: List of source dicts with 'title', 'url', 'body'
        topic: The research topic

    Returns:
        Source accuracy score between 0 and 1
    """
    if not sources:
        return 0.0

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

    source_context = "\n".join([
        f"- {i+1}. {s.get('title', 'Unknown')}: {s.get('href', s.get('url', 'N/A'))}\n   {s.get('body', '')[:200]}"
        for i, s in enumerate(sources[:10])
    ])

    prompt = f"""你是一个评估专家。请评估以下来源的准确性和质量。

研究主题: {topic}

来源列表:
{source_context}

请从以下维度评估：
1. 来源是否与主题相关
2. 来源标题是否准确反映内容
3. 来源是否为可信的网站（政府、学术、知名媒体）
4. 来源内容是否提供了实质性信息

请给出0-1之间的分数，0表示来源质量差，1表示来源质量优秀。
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
        print(f"Source accuracy evaluation error: {e}")
        return 0.5


def evaluate_source_relevance(
    sources: List[Dict[str, Any]],
    key_points: List[str]
) -> Dict[str, float]:
    """Evaluate how well sources cover the key points.

    Args:
        sources: List of source dicts
        key_points: List of key evaluation points

    Returns:
        Dict with 'coverage_score' and 'diversity_score'
    """
    if not sources:
        return {"coverage_score": 0.0, "diversity_score": 0.0}

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return {"coverage_score": 0.5, "diversity_score": 0.5}

    llm = ChatOpenAI(
        model="qwen3.5-plus",
        temperature=0.0,
        max_tokens=500,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    key_points_str = "\n".join([f"- {kp}" for kp in key_points])
    source_titles = "\n".join([f"- {s.get('title', 'Unknown')}" for s in sources[:10]])

    prompt = f"""你是一个评估专家。请评估来源对关键点的覆盖程度。

关键评估点:
{key_points_str}

来源标题:
{source_titles}

请评估：
1. 覆盖率(0-1)：来源是否覆盖了主要关键评估点
2. 多样性(0-1)：来源是否来自不同的网站/领域

输出格式：
coverage: 0.XX
diversity: 0.XX
"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()

        import re
        cov_match = re.search(r'coverage:\s*0?\.\d+', content, re.IGNORECASE)
        div_match = re.search(r'diversity:\s*0?\.\d+', content, re.IGNORECASE)

        coverage = 0.5
        diversity = 0.5

        if cov_match:
            num_match = re.search(r'0?\.\d+', cov_match.group())
            if num_match:
                coverage = float(num_match.group())

        if div_match:
            num_match = re.search(r'0?\.\d+', div_match.group())
            if num_match:
                diversity = float(num_match.group())

        return {
            "coverage_score": coverage,
            "diversity_score": diversity
        }
    except Exception as e:
        print(f"Source relevance evaluation error: {e}")
        return {"coverage_score": 0.5, "diversity_score": 0.5}


def evaluate_citation_quality(answer: str, sources: List[Dict[str, Any]]) -> float:
    """Evaluate whether the answer properly cites sources.

    Args:
        answer: The generated answer/report
        sources: List of source dicts

    Returns:
        Citation quality score between 0 and 1
    """
    if not sources:
        return 0.0

    # Check basic citation patterns
    source_domains = set()
    for s in sources:
        url = s.get('href', s.get('url', ''))
        if url:
            # Extract domain
            import re
            match = re.search(r'https?://([^/]+)', url)
            if match:
                source_domains.add(match.group(1))

    # Count how many source domains are mentioned in the answer
    mentioned_domains = 0
    for domain in source_domains:
        # Simple check - see if domain appears in answer
        if domain.replace('www.', '') in answer.lower().replace('www.', ''):
            mentioned_domains += 1

    # Score based on domain mention rate
    if source_domains:
        return min(mentioned_domains / len(source_domains), 1.0)

    return 0.5


def batch_evaluate_source_accuracy(
    results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Evaluate source accuracy for multiple results.

    Args:
        results: List of dicts with 'topic', 'sources', and optionally 'key_points', 'answer'

    Returns:
        Dict with 'scores', 'average', 'coverage_scores', 'diversity_scores'
    """
    accuracy_scores = []
    coverage_scores = []
    diversity_scores = []
    citation_scores = []

    for result in results:
        sources = result.get("sources", [])
        topic = result.get("topic", "")

        # Source accuracy
        accuracy = evaluate_source_accuracy(sources, topic)
        accuracy_scores.append(accuracy)

        # Source coverage and diversity if key_points provided
        if result.get("key_points"):
            coverage_div = evaluate_source_relevance(sources, result["key_points"])
            coverage_scores.append(coverage_div["coverage_score"])
            diversity_scores.append(coverage_div["diversity_score"])

        # Citation quality if answer provided
        if result.get("answer"):
            citation = evaluate_citation_quality(result["answer"], sources)
            citation_scores.append(citation)

    return {
        "accuracy_scores": accuracy_scores,
        "coverage_scores": coverage_scores if coverage_scores else [0.0] * len(accuracy_scores),
        "diversity_scores": diversity_scores if diversity_scores else [0.0] * len(accuracy_scores),
        "citation_scores": citation_scores if citation_scores else [0.0] * len(accuracy_scores),
        "average_accuracy": sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0,
        "average_coverage": sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0,
        "average_diversity": sum(diversity_scores) / len(diversity_scores) if diversity_scores else 0.0,
        "average_citation": sum(citation_scores) / len(citation_scores) if citation_scores else 0.0
    }
