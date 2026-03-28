"""Tools for the Research Agent."""
import ast
import operator

from langchain_core.tools import tool
from duckduckgo_search import DDGS

# Supported operators for safe AST evaluation
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval_expr(node: ast.AST) -> float:
    """Safely evaluate a mathematical expression AST node.

    Only supports numbers, basic arithmetic operators (+, -, *, /, **), and
    unary negation. No function calls, variables, or other dangerous operations.
    """
    if isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return node.value
    elif isinstance(node, ast.BinOp):
        left = _safe_eval_expr(node.left)
        right = _safe_eval_expr(node.right)
        return _OPERATORS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp):
        operand = _safe_eval_expr(node.operand)
        return _OPERATORS[type(node.op)](operand)
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


@tool
def search_tool(query: str) -> str:
    """Search the web for information using DuckDuckGo.

    Args:
        query: The search query string.

    Returns:
        Search results as a string.
    """
    try:
        results = list(DDGS().text(query, max_results=5))
        formatted = []
        for r in results:
            formatted.append(f"- {r['title']}: {r['href']}\n  {r['body']}")
        return "\n".join(formatted) if formatted else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def calculator_tool(expression: str) -> str:
    """Evaluate a mathematical expression using safe AST evaluation.

    Args:
        expression: A mathematical expression string (e.g., "2 + 2", "10 * 5").

    Returns:
        The result of the calculation as a string.
    """
    try:
        # Security: only allow safe mathematical operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters in expression"

        # Parse and evaluate using safe AST (no eval())
        node = ast.parse(expression, mode="eval")
        result = _safe_eval_expr(node.body)
        return str(result)
    except Exception as e:
        return f"Calculation error: {type(e).__name__}: {e}"


@tool
def save_markdown_tool(content: str, filename: str) -> str:
    """Save markdown content to a file.

    Args:
        content: The markdown content to save.
        filename: The filename to save as (e.g., "my_report.md").

    Returns:
        The full path to the saved file.
    """
    import os

    # Ensure outputs directory exists
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath
