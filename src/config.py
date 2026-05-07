"""
配置管理模块 — 负责加载 YAML 配置文件并合并环境变量覆盖。

配置优先级（从低到高）：
  1. config/default.yaml（默认值）
  2. 环境变量（前缀 PAPER_ASSIST_）
"""

import os
import yaml
from pathlib import Path
from typing import Any
from dotenv import load_dotenv


# 项目根目录（src/config.py 的上级目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 默认配置文件路径
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"

# 已加载的配置缓存
_config_cache: dict[str, Any] | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    """加载 YAML 配置文件（安全模式）。"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _apply_env_overrides(config: dict, prefix: str = "PAPER_ASSIST_") -> dict:
    """
    将匹配前缀的环境变量覆盖到配置字典中。

    环境变量命名规则：
      PAPER_ASSIST_SECTION_KEY=value
    对应配置路径：
      config["section"]["key"] = value

    支持两层嵌套（section.key），深层嵌套暂不支持。
    """
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue

        # 去掉前缀，转换为小写并用 . 分割
        full_path = env_key[len(prefix):].lower()
        parts = full_path.split("_", 1)

        if len(parts) == 2:
            section, key = parts
            if section in config and isinstance(config[section], dict):
                # 尝试类型转换
                config[section][key] = _coerce_env_value(env_value)
        elif len(parts) == 1:
            # 顶级 key
            config[parts[0]] = _coerce_env_value(env_value)

    return config


def _coerce_env_value(value: str) -> Any:
    """将环境变量字符串值转换为合适的 Python 类型。"""
    # 布尔值
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    # 整数
    try:
        return int(value)
    except ValueError:
        pass
    # 浮点数
    try:
        return float(value)
    except ValueError:
        pass
    # 字符串
    return value


def load_config(config_path: Path | None = None, reload: bool = False) -> dict[str, Any]:
    """
    加载系统配置。

    Args:
        config_path: 自定义 YAML 配置文件路径，默认使用 config/default.yaml
        reload: 是否强制重新加载（忽略缓存）

    Returns:
        合并后的配置字典
    """
    global _config_cache

    if _config_cache is not None and not reload:
        return _config_cache

    # 1. 加载 .env 文件（如果存在）
    dotenv_path = PROJECT_ROOT / "config" / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    # 2. 加载默认 YAML
    yaml_path = config_path or DEFAULT_CONFIG_PATH
    if not yaml_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {yaml_path}")

    config = _load_yaml(yaml_path)

    # 3. 合并环境变量覆盖
    config = _apply_env_overrides(config)

    _config_cache = config
    return config


def get_config(key_path: str, default: Any = None) -> Any:
    """
    获取配置中的特定值（支持点号路径）。

    Args:
        key_path: 配置路径，如 "database.path" 或 "rag.retrieval_top_k"
        default: 当路径不存在时的默认返回值

    Returns:
        配置值

    Example:
        >>> db_path = get_config("database.path")
        >>> top_k = get_config("rag.retrieval_top_k", 10)
    """
    config = load_config()
    keys = key_path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def get_data_path(sub_path: str) -> Path:
    """
    获取数据子目录的绝对路径，若目录不存在则自动创建。

    Args:
        sub_path: 相对于项目根目录的数据子路径，如 "data/pdf"

    Returns:
        绝对路径 Path 对象
    """
    full_path = PROJECT_ROOT / sub_path
    full_path.mkdir(parents=True, exist_ok=True)
    return full_path
