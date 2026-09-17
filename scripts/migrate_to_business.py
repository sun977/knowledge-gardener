"""
待审核 → 业务目录迁移（不走 lib/writer.py，因为涉及跨文档操作）。

用途：将人工在 [05]待人工审核 中标记为"已审批"的条目，合并到业务目录（01-05）。

⚠️ 输入源约束（硬性规则，禁止违反）：
本脚本的唯一合法输入源是 `PENDING_REVIEW_CONTENT_ID`（[05]待人工审核）中
已标记"已审批"的行，**不是** [04]优化建议。参见
references/approval-workflow.md 中"两条独立通道"的说明。

安全规则：
1. 必须先确认审批状态为"已审批"，否则拒绝执行（见 assert_approved）
2. 合并前必须做 diff 比对（见 build_diff_preview）
3. 合并后必须保留源文档，不删除（只把源条目状态改为"已合并至 XX"）

本脚本不直接访问学城 API：读取待迁移内容、写入目标目录、更新源条目状态，
均由 Agent 调用 citadel CLI 完成；本脚本只负责校验审批状态、生成 diff 预览、
生成状态更新所需的文本片段。
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.content_ids import PENDING_REVIEW_CONTENT_ID

APPROVED_STATUS = "已审批"


class MigrationBlockedError(Exception):
    """迁移被安全规则拦截"""


def assert_approved(pending_row: dict) -> None:
    """
    确认待迁移条目的审批状态。

    Args:
        pending_row: 从 [05]待人工审核 索引表中读到的一行，
            形如 {'date', 'content_summary', 'target_dir', 'status'}

    Raises:
        MigrationBlockedError: 状态不是"已审批"时拒绝执行
    """
    status = pending_row.get("status")
    if status != APPROVED_STATUS:
        raise MigrationBlockedError(
            f"条目《{pending_row.get('content_summary', '未命名')}》当前状态为"
            f"「{status}」，不是「{APPROVED_STATUS}」，禁止执行迁移。"
            f"必须人工先在 [05]待人工审核（contentId={PENDING_REVIEW_CONTENT_ID}）"
            f"中确认审批后才能迁移。"
        )


def build_diff_preview(source_content: str, target_existing_content: str) -> dict:
    """
    生成合并前的 diff 预览，供 Agent 展示给用户确认。

    Args:
        source_content: 待迁移的内容（来自待人工审核详情/关联记录）
        target_existing_content: 目标业务目录文档中已有的相关内容（如果是新增，传空串）

    Returns:
        {'is_new': bool, 'source_preview': str, 'target_preview': str}
    """
    is_new = not target_existing_content.strip()
    return {
        "is_new": is_new,
        "source_preview": source_content,
        "target_preview": target_existing_content,
        "message": (
            "目标目录暂无相关内容，将作为新增写入"
            if is_new
            else "目标目录已有相关内容，请人工确认合并方式（追加/替换）后再继续"
        ),
    }


def build_source_status_update(pending_row: dict, target_dir: str) -> str:
    """
    生成源条目（待人工审核索引表对应行）状态更新后的文本，
    Agent 据此在 XML 中把该行的状态列替换为此文本。
    """
    return f"已合并至 {target_dir}"


def build_version_log_entry(content_summary: str, target_dir: str, now: datetime = None) -> str:
    """
    生成知识库元信息版本日志新增行，格式遵循已有列顺序
    （版本/日期/变更内容/维护人），维护人固定标注为 Agent。

    注意：版本号（如 v2.1）由 Agent 根据当前最新版本号递增后填入，
    本函数只负责拼接"日期 / 变更内容 / 维护人"三列内容供 Agent 组装。
    """
    now = now or datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    return f"| {date_str} | [Agent] 待人工审核迁移：{content_summary} → {target_dir} | Agent |"


def main(pending_row: dict, source_content: str, target_existing_content: str = "") -> dict:
    """
    执行迁移前置校验，生成 Agent 后续操作所需的全部文本片段。

    Args:
        pending_row: [05]待人工审核 索引表中的一行
            （必须包含 date / content_summary / target_dir / status）
        source_content: 待迁移的完整内容（来自经验沉淀/踩坑记录详情章节等）
        target_existing_content: 目标业务目录中已有的相关内容（新增场景传空串）

    Returns:
        成功: {
            'success': True,
            'diff_preview': {...},
            'source_status_update': str,   # 源条目状态应更新为的文本
            'version_log_entry': str,      # 知识库元信息版本日志新增行
            'target_dir': str,
        }
        失败（审批状态不满足）: {'success': False, 'message': str}
    """
    try:
        assert_approved(pending_row)
    except MigrationBlockedError as e:
        return {"success": False, "message": str(e)}

    target_dir = pending_row["target_dir"]
    content_summary = pending_row["content_summary"]

    diff_preview = build_diff_preview(source_content, target_existing_content)

    return {
        "success": True,
        "diff_preview": diff_preview,
        "source_status_update": build_source_status_update(pending_row, target_dir),
        "version_log_entry": build_version_log_entry(content_summary, target_dir),
        "target_dir": target_dir,
        "message": (
            "前置校验通过。请 Agent 依次执行："
            "1) 展示 diff_preview 给用户确认；"
            "2) 在目标业务目录创建/更新对应文档；"
            "3) 用 source_status_update 更新 [05]待人工审核 源条目状态列（保留源文档不删除）；"
            "4) 用 version_log_entry 追加知识库元信息版本日志。"
        ),
    }


if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        payload = json.loads(sys.argv[1])
        print(json.dumps(main(**payload), ensure_ascii=False, indent=2))
    else:
        demo = main(
            pending_row={
                "date": "2026-08-01",
                "content_summary": "学城写入统一走 render_entry 的经验已验证 5 次，建议转正",
                "target_dir": "03-系统对接规范",
                "status": "已审批",
            },
            source_content="经验沉淀详情：先 getDocumentXml 再改 XML 最后 updateDocumentByXml……",
            target_existing_content="",
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
