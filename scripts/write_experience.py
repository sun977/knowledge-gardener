"""
写入经验沉淀（[02]经验沉淀，contentId 见 lib/content_ids.py）。

用途：Agent 主动建议 + 用户确认后（手动触发），归纳总结一条可复用的经验。

特殊逻辑：同一 `scene` 再次出现时，视为对已有记录追加验证次数——只更新
索引表 `count` 列，不新建重复的详情章节。本脚本负责渲染新纪录的两段内容；
"是否已存在同名 scene"的判断和"只更新 count 列"的差异化处理由 Agent 在
读取 getDocumentXml 结果后自行决定（脚本无法读取线上文档，不做该判断）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.content_ids import EXPERIENCE_CONTENT_ID
from lib.writer import ApiError, KnowledgeWriter, QualityCheckError, TemplateError


def main(
    scene: str,
    summary: str,
    steps: list,
    why_works: str,
    conditions: list,
    source_logs: list,
    count: int = 1,
    status: str = "验证中",
) -> dict:
    """
    Args:
        scene: 适用场景描述（同时作为索引行摘要和详情章节标题）
        summary: 一句话经验摘要（仅索引行）
        steps: 标准操作步骤（仅详情章节）
        why_works: 为什么有效（仅详情章节）
        conditions: 适用边界条件（仅详情章节）
        source_logs: 来源学习日志的链接列表（仅详情章节）
        count: 验证次数（索引行），首次提交默认 1
        status: 索引行状态列，默认"验证中"

    Returns:
        成功: {'success': True, 'content_id', 'row', 'detail', 'message'}
        失败: {'success': False, 'message', 'retryable'}
    """
    writer = KnowledgeWriter()

    try:
        context = {
            "scene": scene,
            "summary": summary,
            "steps": steps or [],
            "why_works": why_works,
            "conditions": conditions or [],
            "source_logs": source_logs or [],
            "count": count,
            "status": status,
        }

        errors = writer.quality_check("experience", context)
        if errors:
            raise QualityCheckError(str(errors))

        entry = writer.render_entry("experience", context)

        return {
            "success": True,
            "content_id": EXPERIENCE_CONTENT_ID,
            "row": entry["row"],
            "detail": entry["detail"],
            "message": (
                "模板渲染完成。若 scene 在索引表中已存在，"
                "请只更新该行 count 列，不要重复插入 detail；"
                "否则同时插入索引行与详情章节。"
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
            scene="学城文档批量追加写入",
            summary="先 getDocumentXml 再本地改 XML 最后 updateDocumentByXml，禁止用简化 Markdown 直接回写",
            steps=[
                "调用 getDocumentXml 拉取当前文档",
                "本地修改 XML：索引表插入新 <tr>，详情章节追加新 <h2> 块",
                "调用 updateDocumentByXml 回写，带上 stepVersion",
            ],
            why_works="保留原有 nodeId 和文档结构，避免学城富文本渲染错乱",
            conditions=["仅适用于已有固定表结构的文档", "不适用于新建文档"],
            source_logs=["学习日志 2026-08-18 条目"],
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
