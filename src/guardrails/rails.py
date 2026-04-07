"""Guardrails configuration for input/output safety checks."""
import os
import re
import logging
from datetime import datetime
from pathlib import Path


# Dangerous patterns for detection
# Organized by category: SQL Injection, Code Execution, XSS, Path Traversal
DANGEROUS_PATTERNS = [
    # SQL Injection patterns
    r"drop\s+table",
    r"delete\s+from",
    r"drop\s+database",
    r"truncate\s+",
    r"insert\s+into",
    r"update\s+\w+\s+set",
    r"union\s+select",
    r"\bor\b\s*\w+\s*=\s*\w+",  # OR-based injection: OR 1=1, OR id=1
    r"'\s*or\s+'",                # 'OR' injection: 'OR '1'='1
    r"'.*\band\b",                 # AND injection in quotes: ' AND '1'='1
    r"'\s*--",                    # SQL comment injection
    r"copy\s+.*\s+to",
    r"xp_cmdshell",
    r"sp_executesql",
    r"openrowset",
    r"admin\s*'",
    r"exec\s*\(",
    r"execute\s*\(",
    r"DECLARE\s+@",
    r"CAST\s*\(",
    r"0x[0-9a-f]+",

    # Code Execution / RCE patterns
    r"eval\s*\(",
    r"__import__",
    r"os\.system",
    r"os\.popen",
    r"subprocess",
    r"shell\s*=\s*True",
    r"\bopen\s*\(",
    r"\binput\s*\(",
    r"\bcompile\s*\(",
    r"exec\s*\(",
    r"getattr\s*\(",
    r"setattr\s*\(",
    r"pkg_resources",
    r"runpy",
    r"imp\s*\.",
    r"zipfile",
    r"\bexec\s*\(",
    r"\bos\s*\.",

    # Shell metacharacters (command injection — multi-char sequences only)
    r";\s*(?:rm|cat|bash|sh|curl|wget|python|perl|ruby|nc|ncat|socat|chmod|chown|kill|mount|umount|dd|mkfifo)\b",
    r"\|\s*(?:bash|sh|cat|python|perl|ruby|nc|ncat|socat|curl|wget|tee|head|tail|sort|uniq|wc|tr|sed|awk|grep)\b",
    r"`[^`]+`",       # Backtick-wrapped command: `command`
    r"\$\(",          # Command substitution: $(command)
    r"<\(",           # Process substitution: <(command)
    r">\s*/",         # Output redirection to a path: > /tmp/file
    r"\b&\s*$",       # Background execution at word boundary: command&

    # XSS patterns
    r"<\s*script",
    r"javascript:",
    r"<iframe",
    r"onerror\s*=",
    r"onclick\s*=",
    r"onload\s*=",
    r"onfocus\s*=",
    r"onblur\s*=",
    r"onchange\s*=",
    r"onkeydown\s*=",
    r"onkeyup\s*=",
    r"onmouseover\s*=",
    r"onmouseout\s*=",
    r"onsubmit\s*=",
    r"onreset\s*=",
    r"onselect\s*=",
    r"vbscript:",
    r"data:text/html",
    r"\{\{.*\}\}",        # Template injection {{
    r"\$\{.*\}",          # Template injection ${
    r"<svg\s+onload",
    r"<body\s+onload",
    r"<marquee\s+",
    r"alert\s*\(",

    # Path Traversal / File Inclusion
    r"\.\.[/\\]",         # Path traversal ../ or ..\
    r"php://",
    r"data://",
    r"file://",
    r"gopher://",
    r"sftp://",
    r"ftp://",
    r"%00",               # Null byte injection
    r"\.\./",             # Encoded traversal
    r"\.\.%",             # Double encoding
    r"<>\s*",             # Angle brackets
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
