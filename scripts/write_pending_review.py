"""
提交内容转正申请（[05]待人工审核，contentId 见 lib/content_ids.py）。

用途：Agent 主动判断某条自建知识（经验沉淀/踩坑记录中的具体条目）已验证充分，
值得转正进业务目录（01-05），提交转正申请。

本文档字段全部短小，无详情章节，仅渲染索引行。

审批门控：
- 提交后状态标记为"待审批"
- 必须人工确认后才能执行 migrate_to_business.py（唯一合法触发源）
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.content_ids import PENDING_REVIEW_CONTENT_ID
from lib.writer import ApiError, KnowledgeWriter, QualityCheckError, TemplateError


def main(content_summary: str, target_dir: str, source_link: str = None) -> dict:
    """
    Args:
        content_summary: 内容概要（要转正的知识点）
        target_dir: 目标合并目录（01-05 中的某一个）
        source_link: 来源记录链接（经验沉淀/踩坑记录中的具体条目，可选）

    Returns:
        成功: {'success': True, 'content_id', 'row', 'detail': None, 'message'}
        失败: {'success': False, 'message', 'retryable'}
    """
    writer = KnowledgeWriter()

    try:
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "content_summary": content_summary,
            "target_dir": target_dir,
            "source_link": source_link or "",
            "status": "待审批",
        }

        errors = writer.quality_check("pending_review", context)
        if errors:
            raise QualityCheckError(str(errors))

        entry = writer.render_entry("pending-review", context)  # detail 恒为 None

        return {
            "success": True,
            "content_id": PENDING_REVIEW_CONTENT_ID,
            "row": entry["row"],
            "detail": entry["detail"],
            "message": (
                "模板渲染完成，Agent 需将 row 插入索引表（无详情章节）。"
                "状态标记为待审批，需人工确认后才能执行 migrate_to_business.py。"
            ),
        }

    except QualityCheckError as e:
        return {"success": False, "message": f"质量自检失败: {e}", "retryable": True}

    except TemplateError as e:
        return {"success": False, "message": f"模板渲染失败: {e}", "retryable": False}

    except ApiError as e:
        return {"success": False, "message": f"API 调用失败: {e}", "retryable": True}

    except Exception as e:  # noqa: BLE001
        return {"success": False, "message": f"未知错误: {e}", "retryable": False}


if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        payload = json.loads(sys.argv[1])
        print(json.dumps(main(**payload), ensure_ascii=False, indent=2))
    else:
        demo = main(
            content_summary="学城写入统一走 render_entry 的经验已验证 5 次，建议转正",
            target_dir="03-系统对接规范",
            source_link="经验沉淀 - 学城文档批量追加写入",
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
