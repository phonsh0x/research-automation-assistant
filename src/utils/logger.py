"""
统一日志系统 — 基于 Python logging 模块。

功能：
  - 按模块自动创建独立 logger
  - 日志文件按模块和日期分割
  - 同时输出到文件和控制台
  - 从 config/default.yaml 读取日志配置
  - 支持运行时动态修改日志级别
"""

import logging
import sys
from pathlib import Path
from datetime import date
from typing import Optional


# 项目根目录（src/utils/logger.py 的上两级目录）
_LOGGER_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 已初始化的 logger 缓存
_loggers: dict[str, logging.Logger] = {}
# 全局日志系统是否已初始化
_logging_initialized: bool = False


def _get_logging_config() -> dict:
    """从配置文件中读取日志相关配置（避免循环导入）。"""
    try:
        from src.config import load_config
        config = load_config()
        return config.get("logging", {})
    except Exception as e:
        # 配置加载失败（此时日志系统可能尚未就绪，仅返回默认值）
        # 若日志已初始化，记录 debug 信息
        if _logging_initialized:
            logging.getLogger(__name__).debug(f"读取日志配置失败，使用默认值: {e}")
        return {
            "level": "INFO",
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            "date_format": "%Y-%m-%d %H:%M:%S",
            "file_pattern": "{module}_{date}.log",
            "retention_days": 30,
            "console_output": True,
        }


def init_logging() -> None:
    """
    初始化全局日志系统（在应用启动时调用一次）。

    执行后，所有通过 get_logger() 获取的 logger 都将具有正确的配置。
    """
    global _logging_initialized

    if _logging_initialized:
        return

    log_config = _get_logging_config()

    # 日志根 logger 配置
    root_logger = logging.getLogger()
    level_name = log_config.get("level", "INFO")
    root_logger.setLevel(getattr(logging, level_name, logging.INFO))

    # 控制台输出
    if log_config.get("console_output", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level_name, logging.INFO))
        console_formatter = logging.Formatter(
            log_config.get("format", "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"),
            datefmt=log_config.get("date_format", "%Y-%m-%d %H:%M:%S"),
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    _logging_initialized = True


def get_logger(
    module_name: str,
    log_to_file: bool = True,
    file_path: Optional[Path] = None,
) -> logging.Logger:
    """
    获取指定模块的 logger 实例。

    每个模块应使用自己的 logger：
      logger = get_logger(__name__)

    Args:
        module_name: 模块名称（通常传 __name__）
        log_to_file: 是否同时写入日志文件
        file_path: 自定义日志文件路径，默认使用 data/logs/{module}_{date}.log

    Returns:
        Python Logger 实例

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("数据库初始化完成")
        >>> logger.error(f"检索失败: {err}")
    """
    # 确保日志系统已初始化
    if not _logging_initialized:
        init_logging()

    # 如果已有该模块的 logger，直接返回
    if module_name in _loggers:
        return _loggers[module_name]

    log_config = _get_logging_config()
    logger = logging.getLogger(module_name)

    # 文件输出 handler（每个模块独有）
    if log_to_file:
        if file_path is None:
            logs_dir = _LOGGER_PROJECT_ROOT / "data" / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名：{module_name_short}_{date}.log
            module_short = module_name.split(".")[-1]
            today = date.today().isoformat()
            file_pattern = log_config.get("file_pattern", "{module}_{date}.log")
            filename = file_pattern.format(module=module_short, date=today)
            file_path = logs_dir / filename

        file_handler = logging.FileHandler(str(file_path), encoding="utf-8")
        file_handler.setLevel(logger.level or logging.INFO)
        file_formatter = logging.Formatter(
            log_config.get("format", "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"),
            datefmt=log_config.get("date_format", "%Y-%m-%d %H:%M:%S"),
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _loggers[module_name] = logger
    return logger


def set_log_level(level: str) -> None:
    """
    动态修改所有 logger 的日志级别。

    Args:
        level: 日志级别名称，如 "DEBUG", "INFO", "WARNING", "ERROR"
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    for logger in _loggers.values():
        logger.setLevel(log_level)
