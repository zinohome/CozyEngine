"""日志脱敏工具"""

import re
from collections.abc import MutableMapping
from typing import Any

# 敏感字段关键词（不区分大小写）
SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "privatekey",
    "access_token",
    "refresh_token",
    "session_token",
}

# 敏感值模式（正则）
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),  # OpenAI API keys
    re.compile(r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", re.IGNORECASE),  # Bearer tokens
    re.compile(r"[a-zA-Z0-9]{32,}", re.IGNORECASE),  # Long tokens
]

MASK = "***REDACTED***"


def sanitize_log_data(
    data: dict[str, Any] | MutableMapping[str, Any],
) -> dict[str, Any] | MutableMapping[str, Any]:
    """
    脱敏日志数据

    - 移除敏感字段的值
    - 检测并脱敏敏感模式
    """
    if not isinstance(data, (dict, MutableMapping)):
        return data

    sanitized = {} if isinstance(data, dict) else type(data)()
    for key, value in data.items():
        if isinstance(value, (dict, MutableMapping)):
            # 递归处理嵌套字典
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, list):
            # 处理列表
            sanitized[key] = [
                sanitize_log_data(item)
                if isinstance(item, (dict, MutableMapping))
                else (_sanitize_value(item) if isinstance(item, str) else item)
                for item in value
            ]
        elif isinstance(value, str):
            # 检查键是否敏感或值是否包含敏感模式
            if _is_sensitive_key(key):
                sanitized[key] = MASK
            else:
                sanitized[key] = _sanitize_value(value)
        else:
            # 对于非字符串的叶子节点，检查键是否敏感
            if _is_sensitive_key(key):
                sanitized[key] = MASK
            else:
                sanitized[key] = value

    return sanitized


def _is_sensitive_key(key: str) -> bool:
    """检查键是否包含敏感关键词"""
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def _sanitize_value(value: str) -> str:
    """检测并脱敏敏感值"""
    if not isinstance(value, str):
        return value

    for pattern in SENSITIVE_PATTERNS:
        value = pattern.sub(MASK, value)

    return value


def sanitize_pii(text: str) -> str:
    """
    脱敏 PII（个人身份信息）

    - 手机号
    - 邮箱
    - 身份证号
    """
    # 手机号（中国）
    text = re.sub(r"1[3-9]\d{9}", lambda m: m.group()[:3] + "****" + m.group()[-4:], text)

    # 邮箱
    text = re.sub(
        r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        lambda m: m.group(1)[:2] + "***@" + m.group(2),
        text,
    )

    # 身份证号（中国）
    text = re.sub(
        r"\d{17}[\dXx]",
        lambda m: m.group()[:6] + "********" + m.group()[-4:],
        text,
    )

    return text
