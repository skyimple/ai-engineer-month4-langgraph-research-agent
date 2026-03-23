"""LLM Configuration using DashScope API."""
import os
from dotenv import load_dotenv

load_dotenv('config.env')

from langchain_openai import ChatOpenAI

api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("未找到 DASHSCOPE_API_KEY")

# Initialize LLM with DashScope API (qwen3.5-plus model)
llm = ChatOpenAI(
    model="qwen3.5-plus",
    temperature=0.7,
    max_tokens=2048,
    streaming=False,
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def get_llm():
    """Return the configured LLM instance."""
    return llm
