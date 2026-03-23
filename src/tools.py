"""Tools for the Research Agent."""
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient

load_dotenv('config.env')

# Initialize Tavily client
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


@tool
def search_tool(query: str) -> str:
    """Search the web for information using Tavily.

    Args:
        query: The search query string.

    Returns:
        Search results as a string.
    """
    try:
        results = tavily_client.search(query=query, max_results=5)
        # Format results nicely
        formatted = []
        for r in results.get("results", []):
            formatted.append(f"- {r.get('title', 'No title')}: {r.get('url', '')}\n  {r.get('content', '')}")
        return "\n".join(formatted) if formatted else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def calculator_tool(expression: str) -> str:
    """Evaluate a mathematical expression.

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
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"
