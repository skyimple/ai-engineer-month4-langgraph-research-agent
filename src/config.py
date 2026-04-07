"""LLM Configuration using DashScope API."""
import os
from dotenv import load_dotenv

load_dotenv('config.env')

from langchain_openai import ChatOpenAI
from langsmith import traceable

# ============== LangSmith 配置 ==============
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "research-agent")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

# ============== Phoenix 配置 ==============
PHOENIX_AVAILABLE = False
PHOENIX_TRACING_ENABLED = False

try:
    import phoenix as px
    from phoenix.otel import register
    PHOENIX_AVAILABLE = True
except ImportError:
    pass

def setup_phoenix():
    """初始化 Phoenix 追踪（生产环境友好）"""
    global PHOENIX_TRACING_ENABLED
    if not PHOENIX_AVAILABLE:
        print("Phoenix: phoenix 包未安装，跳过")
        return

    # 默认禁用 Phoenix（需要通过设置 PHOENIX_ENDPOINT 来启用）
    disable_phoenix = os.getenv("DISABLE_PHOENIX", "1").lower()
    if disable_phoenix in ("1", "true", "yes"):
        print("Phoenix: 默认禁用（设置 PHOENIX_ENDPOINT 环境变量来启用）")
        return

    try:
        # 配置 OTEL 导出到 Phoenix
        # 优先使用 PHOENIX_ENDPOINT（自托管 Phoenix）
        # 本地模式: http://localhost:6006/v1/traces
        # 云端模式: 需要设置 PHOENIX_API_KEY 环境变量
        endpoint = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces")

        print(f"Phoenix: 正在连接到 {endpoint}...")

        tracer_provider = register(
            project_name=LANGCHAIN_PROJECT,
            endpoint=endpoint
        )

        # 设置 LangChain 追踪
        from openinference.instrumentation.langchain import LangChainInstrumentor
        LangChainInstrumentor().instrument()

        PHOENIX_TRACING_ENABLED = True
        print("Phoenix: tracing 已启用")
    except Exception as e:
        print(f"Phoenix: 初始化失败 ({type(e).__name__}: {e})")
        print("Phoenix: 继续运行，不影响主要功能")
        PHOENIX_TRACING_ENABLED = False

# ============== A/B Testing 配置 ==============
AB_TEST_PROMPT_VERSION = os.getenv("AB_TEST_PROMPT_VERSION", "A")
AB_TEST_MODEL_A = os.getenv("AB_TEST_MODEL_A", "qwen3.5-plus")
AB_TEST_MODEL_B = os.getenv("AB_TEST_MODEL_B", "qwen3.5-plus")

# ============== LLM 初始化 ==============
import threading

_llm = None
_llm_lock = threading.Lock()

def get_llm():
    """Return the configured LLM instance (lazy initialization, thread-safe)."""
    global _llm
    if _llm is None:
        with _llm_lock:
            if _llm is None:
                api_key = os.getenv("DASHSCOPE_API_KEY")
                if not api_key:
                    raise ValueError("未找到 DASHSCOPE_API_KEY")
                _llm = ChatOpenAI(
                    model="qwen3.5-plus",
                    temperature=0.7,
                    max_tokens=2048,
                    streaming=False,
                    api_key=api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )
    return _llm

def get_llm_for_ab_version(version: str = None):
    """Return LLM instance for A/B testing."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未找到 DASHSCOPE_API_KEY")
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
