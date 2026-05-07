"""
写作辅助模块 — 中文学术写作助手。

职责：
  - 文献综述辅助（检索相关文献并生成综述段落）
  - 基金申请书辅助（立项依据、研究内容、特色创新）
  - 论文章节辅助（摘要、引言、方法、实验、讨论）
  - 文字润色与规范检查
  - 参考文献格式规范化

参考 scientific-writing-assistant-cn skill 规范。
"""

from src.writing_assist.assistant import WritingAssistant

__all__ = ["WritingAssistant"]
