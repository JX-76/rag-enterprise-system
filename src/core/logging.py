"""
Logging Configuration - 日志配置
支持结构化日志和TraceID追踪
"""
import sys
import logging
from typing import Any, Dict

try:
    import structlog  # type: ignore
    HAS_STRUCTLOG = True
except ImportError:
    structlog = None  # type: ignore
    HAS_STRUCTLOG = False


class _FallbackLogger:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def info(self, *args, **kwargs):
        self._logger.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self._logger.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        self._logger.error(*args, **kwargs)

    def debug(self, *args, **kwargs):
        self._logger.debug(*args, **kwargs)

    def bind(self, **kwargs):
        return self


def setup_logging(log_level: str = "INFO") -> None:
    """配置日志，优先使用structlog，缺失时降级到标准logging。"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    if HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


def get_logger(name: str):
    """获取logger实例。"""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return _FallbackLogger(name)
