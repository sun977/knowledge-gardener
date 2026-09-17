"""
写入踩坑记录（[03]踩坑记录，contentId 见 lib/content_ids.py）。

用途：遇到错误或异常时，追写一条踩坑记录。
无自动计数，用户手动提交即可；同一场景第 3 次出现时，
调用方可在 context 中传入 high_frequency=True 和 frequency=次数，
详情章节会自动标注"⚠️ 高频坑"。
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.content_ids import PITFALL_CONTENT_ID
from lib.writer import ApiError, KnowledgeWriter, QualityCheckError, TemplateError


def main(
    scene: str,
    error_msg: str,
    root_cause: str,
    solution: str,
    prevention: str,
    status: str = "已解决",
    high_frequency: bool = False,
    frequency: int = None,
) -> dict:
    """
    Args:
        scene: 错误场景（同时作为索引行摘要）
        error_msg: 错误信息（原始报错，可多行，用代码块承载于详情章节）
        root_cause: 原因分析（仅详情章节）
        solution: 解决方案（仅详情章节）
        prevention: 预防建议（仅详情章节）
        status: 索引行状态列，默认"已解决"
        high_frequency: 是否标注为高频坑（同类错误已出现≥3次时传 True）
        frequency: 该类型错误出现次数（配合 high_frequency 使用）

    Returns:
        成功: {'success': True, 'content_id', 'row', 'detail', 'message'}
        失败: {'success': False, 'message', 'retryable'}
    """
    writer = KnowledgeWriter()

    try:
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "scene": scene,
            "error_msg": error_msg,
            "root_cause": root_cause,
            "solution": solution,
            "prevention": prevention,
            "status": status,
            "high_frequency": high_frequency,
            "frequency": frequency,
        }

        errors = writer.quality_check("pitfall", context)
        if errors:
            raise QualityCheckError(str(errors))

        entry = writer.render_entry("pitfall", context)

        return {
            "success": True,
            "content_id": PITFALL_CONTENT_ID,
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

    except Exception as e:  # noqa: BLE001
        return {"success": False, "message": f"未知错误: {e}", "retryable": False}


if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        payload = json.loads(sys.argv[1])
        print(json.dumps(main(**payload), ensure_ascii=False, indent=2))
    else:
        demo = main(
            scene="citadel CLI 未安装导致调用失败",
            error_msg="'oa-skills' is not recognized as an internal or external command",
            root_cause="全局环境未安装 @it/oa-skills 包",
            solution="npm install -g @it/oa-skills",
            prevention="任务开始前先检查 CLI 是否可用",
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
