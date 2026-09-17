"""
06-Agent自建知识（父目录 contentId: 2780936747）下 5 个子文档的真实 contentId。

这些文档已在线上建好固定表结构（索引表 + 详情章节），脚本只做追加写入，
不新建同类文档，也不修改父目录之外的任何内容。
"""

PARENT_CONTENT_ID = "2780936747"  # 06-Agent自建知识

LEARNING_LOG_CONTENT_ID = "2780767955"    # [01]学习日志（索引表+详情章节）
EXPERIENCE_CONTENT_ID = "2781086741"      # [02]经验沉淀（索引表+详情章节）
PITFALL_CONTENT_ID = "2781216217"         # [03]踩坑记录（索引表+详情章节）
OPTIMIZATION_CONTENT_ID = "2781276182"    # [04]优化建议（索引表+详情章节）
PENDING_REVIEW_CONTENT_ID = "2781426045"  # [05]待人工审核（纯索引表，无详情章节）
