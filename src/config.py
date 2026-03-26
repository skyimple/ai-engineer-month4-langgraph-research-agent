"""LLM Configuration using DashScope API."""
import os
from dotenv import load_dotenv

load_dotenv('config.env')

from langchain_openai import ChatOpenAI
from langsmith import traceable

api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("未找到 DASHSCOPE_API_KEY")

# ============== LangSmith 配置 ==============
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "research-agent")
os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY or ""
os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT

# ============== Phoenix 配置 ==============
try:
    import phoenix as px
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    px = None

def setup_phoenix():
    """初始化 Phoenix（可选）"""
    if PHOENIX_AVAILABLE:
        px.launch_app()

# ============== A/B Testing 配置 ==============
AB_TEST_PROMPT_VERSION = os.getenv("AB_TEST_PROMPT_VERSION", "A")
AB_TEST_MODEL_A = os.getenv("AB_TEST_MODEL_A", "qwen3.5-plus")
AB_TEST_MODEL_B = os.getenv("AB_TEST_MODEL_B", "qwen3.5-plus")

# ============== LLM 初始化 ==============
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

def get_llm_for_ab_version(version: str = None):
    """Return LLM instance for A/B testing."""
    version = version or AB_TEST_PROMPT_VERSION
    model_name = AB_TEST_MODEL_B if version == "B" else AB_TEST_MODEL_A
    return ChatOpenAI(
        model=model_name,
        temperature=0.7,
        max_tokens=2048,
        streaming=False,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
