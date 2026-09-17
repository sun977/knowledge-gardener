"""
写入学习日志（[01]学习日志，contentId 见 lib/content_ids.py）。

用途：每次任务结束后，追写一条新的学习记录。
本脚本只负责「构造数据 + 质量自检 + 模板渲染」，返回 {row, detail} 两段内容；
真正把内容写入学城文档由 Agent 调用 citadel CLI 完成
（getDocumentXml → 同时插入索引行与详情章节 → updateDocumentByXml）。
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.content_ids import LEARNING_LOG_CONTENT_ID
from lib.writer import ApiError, KnowledgeWriter, QualityCheckError, TemplateError


def main(
    task_type: str,
    task_summary: str,
    execution_review: str,
    good_points: list,
    improvements: list,
    linked_docs: list = None,
) -> dict:
    """
    Args:
        task_type: 任务类型（审计排查/数据分析/报告生成/系统操作）
        task_summary: 任务概要（1-2 句，同时作为索引行摘要）
        execution_review: 执行过程回顾（仅详情章节使用）
        good_points: 做得好的地方（列表，仅详情章节使用）
        improvements: 可以改进的地方（列表，即使没有也要写"暂无"）
        linked_docs: 关联文档链接（可选）

    Returns:
        成功: {'success': True, 'content_id', 'row', 'detail', 'message'}
        失败: {'success': False, 'message', 'retryable'}
    """
    writer = KnowledgeWriter()

    try:
        # 1. 构造数据
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "task_type": task_type,
            "task_summary": task_summary,
            "execution_review": execution_review,
            "good_points": good_points or [],
            "improvements": improvements or ["暂无"],
            "linked_docs": linked_docs or [],
        }

        # 2. 质量自检
        errors = writer.quality_check("learning_log", context)
        if errors:
            raise QualityCheckError(str(errors))

        # 3. 渲染模板（同时得到索引行和详情章节两段内容）
        entry = writer.render_entry("learning-log", context)

        # 4. 返回渲染结果（给 Agent）
        # Agent 负责调用 citadel CLI，把 entry['row'] 插入索引表末尾，
        # 把 entry['detail'] 插入详情记录章节末尾
        return {
            "success": True,
            "content_id": LEARNING_LOG_CONTENT_ID,
            "row": entry["row"],
            "detail": entry["detail"],
            "message": "模板渲染完成，请调用 citadel 同时写入索引行和详情章节",
        }

    except QualityCheckError as e:
        return {"success": False, "message": f"质量自检失败: {e}", "retryable": True}

    except TemplateError as e:
        return {"success": False, "message": f"模板渲染失败: {e}", "retryable": False}

    except ApiError as e:
        return {"success": False, "message": f"API 调用失败: {e}", "retryable": True}

    except Exception as e:  # noqa: BLE001 — 兜底捕获，返回给调用方而非抛出
        return {"success": False, "message": f"未知错误: {e}", "retryable": False}


if __name__ == "__main__":
    import json

    # 简单的命令行自测入口：
    #   python write_learning_log.py '{"task_type": "...", ...}'
    if len(sys.argv) > 1:
        payload = json.loads(sys.argv[1])
        print(json.dumps(main(**payload), ensure_ascii=False, indent=2))
    else:
        demo = main(
            task_type="审计排查",
            task_summary="排查某表口径异常并修正 SQL",
            execution_review="先核对指标定义，再逐层下钻定位到过滤条件遗漏。",
            good_points=["优先核对指标口径，减少返工"],
            improvements=["暂无"],
            linked_docs=[],
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
