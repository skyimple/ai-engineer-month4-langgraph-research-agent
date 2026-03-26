"""Guardrails configuration for input/output safety checks."""
import os
import re
import logging
from datetime import datetime
from pathlib import Path


# Dangerous patterns for detection
DANGEROUS_PATTERNS = [
    r"drop\s+table",
    r"delete\s+from",
    r"drop\s+database",
    r"truncate\s+",
    r"exec\s*\(",
    r"eval\s*\(",
    r"__import__",
    r"os\.system",
    r"subprocess",
    r"shell\s*=\s*True",
    r"<\s*script",
    r"javascript:",
    r"<iframe",
    r"onerror\s*=",
    r"onclick\s*=",
]


def _setup_logger():
    """Set up guardrails logger with daily rotation."""
    log_dir = Path("logs/guardrails_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"guardrails_{today}.log"

    logger = logging.getLogger("guardrails")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def _check_patterns(text: str) -> tuple[bool, str]:
    """Check text against dangerous patterns. Returns (is_safe, message)."""
    text_lower = text.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, f"检测到危险模式: {pattern}"
    return True, ""


def check_input_guardrails(user_input: str) -> tuple[bool, str]:
    """
    Check user input for malicious content.

    Args:
        user_input: The user-provided input string

    Returns:
        tuple[bool, str]: (is_safe, safety_message)
            - If safe: (True, "")
            - If unsafe: (False, safety_notice)
    """
    logger = _setup_logger()
    logger.info(f"检查输入: {user_input[:100]}...")

    # Empty input check
    if not user_input or not user_input.strip():
        logger.warning("空输入被拦截")
        return False, "输入不能为空"

    # Check against dangerous patterns
    is_safe, message = _check_patterns(user_input)

    if not is_safe:
        logger.warning(f"危险输入被拦截: {message}")
        safety_notice = (
            "\n" + "=" * 60 + "\n"
            "⚠️  安全警告：输入包含潜在危险内容\n"
            "=" * 60 + "\n"
            "您的输入已被安全系统拦截。\n"
            "请勿尝试注入恶意代码或命令。\n"
            "=" * 60 + "\n"
        )
        return False, safety_notice

    logger.info("输入检查通过")
    return True, ""


def check_output_guardrails(output: str) -> tuple[bool, str]:
    """
    Check output content for safety issues.

    Args:
        output: The output content to check

    Returns:
        tuple[bool, str]: (is_safe, safety_message)
            - If safe: (True, "")
            - If unsafe: (False, safety_notice)
    """
    logger = _setup_logger()
    logger.info(f"检查输出长度: {len(output)} 字符")

    # Empty output check
    if not output or not output.strip():
        logger.warning("空输出被拦截")
        return False, "输出内容不能为空"

    # Check for potentially harmful content patterns
    is_safe, message = _check_patterns(output)

    if not is_safe:
        logger.warning(f"危险输出被拦截: {message}")
        safety_notice = (
            "\n" + "=" * 60 + "\n"
            "⚠️  安全警告：输出包含潜在危险内容\n"
            "=" * 60 + "\n"
            "系统生成的输出已被安全系统拦截。\n"
            "=" * 60 + "\n"
        )
        return False, safety_notice

    logger.info("输出检查通过")
    return True, ""
