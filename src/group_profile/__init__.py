"""
课题组画像模块 — 分析课题组已发表论文，生成研究方向画像。

职责：
  - 课题组论文标记与管理
  - 研究方向自动抽取（TF-IDF / BERTopic / LLM 辅助）
  - 关键词云和主题演化趋势
  - 合作者网络构建与可视化
  - Markdown 画像报告生成

参考 research-group-profiler skill 规范。
"""

from src.group_profile.profiler import GroupProfiler

__all__ = ["GroupProfiler"]
