"""Faithfulness metric: Evaluates whether the answer is faithful to the reference sources."""

from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv('config.env')


def evaluate_faithfulness(answer: str, sources: List[Dict[str, Any]], topic: str) -> float:
    """Evaluate faithfulness score (0-1) based on how well the answer aligns with sources.

    Args:
        answer: The generated answer/report
        sources: List of source dicts with 'title', 'url', 'body'
        topic: The research topic

    Returns:
        Faithfulness score between 0 and 1
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

    # Build context from sources
    source_context = "\n".join([
        f"- {s.get('title', 'Unknown')}: {s.get('body', '')}"
        for s in sources[:10]  # Limit to top 10 sources
    ])

    prompt = f"""你是一个评估专家。请评估以下答案是否忠实于参考资料。

研究主题: {topic}

参考答案:
{answer}

参考资料:
{source_context}

请评估答案是否：
1. 基于参考资料中的信息（而非凭空编造）
2. 没有错误地描述参考资料中的事实
3. 没有添加参考资料中没有的信息作为事实

请给出0-1之间的分数，0表示完全不忠实，1表示完全忠实。
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
        print(f"Faithfulness evaluation error: {e}")
        return 0.5


def batch_evaluate_faithfulness(
    results: List[Dict[str, Any]]
) -> Dict[str, float]:
    """Evaluate faithfulness for multiple results.

    Args:
        results: List of dicts with 'topic', 'answer', 'sources'

    Returns:
        Dict with 'scores' (list) and 'average' (float)
    """
    scores = []
    for result in results:
        score = evaluate_faithfulness(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            topic=result.get("topic", "")
        )
        scores.append(score)

    return {
        "scores": scores,
        "average": sum(scores) / len(scores) if scores else 0.0
    }
