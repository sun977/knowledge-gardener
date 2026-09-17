"""
提交优化建议（[04]优化建议，contentId 见 lib/content_ids.py）。

用途：Agent 主动建议 + 用户确认后（手动触发），针对「流程/规范」提交改进建议。

⚠️ 重要边界：优化建议 与 待人工审核 是两条独立通道，不是前后串联关系。
- 本脚本（优化建议）：针对"流程/做法"的改进意见，审批通过后由人工手动调整对应
  SOP/规范文档（该调整动作在业务目录内完成），**不触发** migrate_to_business.py
- 待人工审核（write_pending_review.py）：针对某条"知识内容"本身要不要转正进业务
  目录（01-05）的申请，审批通过后才执行 migrate_to_business.py

`migrate_to_business.py` 的唯一合法输入源是 [05]待人工审核，不是本文档。
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.content_ids import OPTIMIZATION_CONTENT_ID
from lib.writer import ApiError, KnowledgeWriter, QualityCheckError, TemplateError


def main(
    target: str,
    current: str,
    proposed: str,
    expected_benefit: list,
    risk_assessment: str,
    evidence: list,
) -> dict:
    """
    Args:
        target: 优化目标（指向哪个流程/规范，同时作为索引行摘要）
        current: 当前做法（仅详情章节）
        proposed: 建议做法（仅详情章节）
        expected_benefit: 预期收益（量化优先，仅详情章节）
        risk_assessment: 风险评估（仅详情章节）
        evidence: 支撑依据（经验/踩坑记录链接，仅详情章节）

    Returns:
        成功: {'success': True, 'content_id', 'row', 'detail', 'message'}
        失败: {'success': False, 'message', 'retryable'}
    """
    writer = KnowledgeWriter()

    try:
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "target": target,
            "current": current,
            "proposed": proposed,
            "expected_benefit": expected_benefit or [],
            "risk_assessment": risk_assessment,
            "evidence": evidence or [],
            "status": "待审批",
        }

        errors = writer.quality_check("optimization", context)
        if errors:
            raise QualityCheckError(str(errors))

        entry = writer.render_entry("optimization", context)

        return {
            "success": True,
            "content_id": OPTIMIZATION_CONTENT_ID,
            "row": entry["row"],
            "detail": entry["detail"],
            "message": (
                "模板渲染完成，状态已标记为待审批。审批通过后由人工手动落地到"
                "对应流程/规范文档，本流程不自动触发 migrate_to_business.py。"
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
            target="学城写入 SOP",
            current="每次写入手动拼接 XML，容易漏改 nodeId",
            proposed="统一走 lib/writer.py 的 render_entry，Agent 只负责插入两处片段",
            expected_benefit=["减少人工拼接 XML 出错率", "写入流程标准化，易于审计"],
            risk_assessment="模板变更需要同步更新 5 个 contentId 对应文档结构，改动前需人工确认",
            evidence=["踩坑记录 2026-08-10：手动拼接 XML 导致 nodeId 冲突"],
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
