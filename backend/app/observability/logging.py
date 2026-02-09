"""结构化日志系统"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, FilteringBoundLogger

from app.utils.sanitize import sanitize_log_data


def configure_logging(log_level: str = "INFO") -> None:
    """配置结构化日志"""

    # 配置标准库的 logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            sanitize_processor,  # 脱敏处理器
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def sanitize_processor(
    _logger: Any, _method_name: str, event_dict: EventDict
) -> EventDict:
    """日志脱敏处理器"""
    return sanitize_log_data(event_dict)


def get_logger(name: str) -> FilteringBoundLogger:
    """获取结构化日志实例"""
    return structlog.get_logger(name)


def bind_request_context(
    request_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
    personality_id: str | None = None,
) -> None:
    """绑定请求上下文到日志"""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        personality_id=personality_id,
    )


def unbind_request_context() -> None:
    """解绑请求上下文"""
    structlog.contextvars.clear_contextvars()
