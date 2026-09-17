"""
知识库健康度巡检（不走 lib/writer.py，因为这是"读取并分析"而非"写入新内容"）。

用途：定期（建议每周）巡检 06-Agent自建知识 各文档，发现过期、死链、冗余、
积压等问题，生成巡检报告后通过 write_learning_log.py 写入学习日志。

数据来源：本脚本不直接访问网络，所有输入数据（各文档的索引表行、版本日志等）
由 Agent 先通过 citadel CLI（getDocumentXml / getSimpleMarkdown）拉取，
解析成结构化数据后传入 main()。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

STALE_DAYS = 30           # 内容过期阈值
BACKLOG_DAYS = 14         # 待审核积压阈值
COVERAGE_STALE_DAYS = 60  # 待补充项过期阈值


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def check_stale_version_log(version_log_rows: list, now: datetime = None) -> list:
    """检查版本日志超过 30 天未更新。

    Args:
        version_log_rows: [{'date': 'YYYY-MM-DD', ...}, ...] 版本日志行，
            调用方传入按时间排序（最新的在最后或最前皆可，函数内部会自行取最大日期）
    """
    now = now or datetime.now()
    dates = [d for d in (_parse_date(r.get("date")) for r in version_log_rows) if d]
    if not dates:
        return [{"item": "内容过期", "severity": "警告", "detail": "版本日志为空或日期缺失"}]

    latest = max(dates)
    if now - latest > timedelta(days=STALE_DAYS):
        return [
            {
                "item": "内容过期",
                "severity": "警告",
                "detail": f"版本日志最近一次更新为 {latest.strftime('%Y-%m-%d')}，"
                f"已超过 {STALE_DAYS} 天未更新",
            }
        ]
    return []


def check_dead_links(rows: list, existing_content_ids: set) -> list:
    """检查索引表中引用的路径/contentId 对应文档是否存在。

    Args:
        rows: [{'linked_content_id': '...', 'summary': '...'}, ...]
        existing_content_ids: 当前已知有效的 contentId 集合
    """
    issues = []
    for row in rows:
        cid = row.get("linked_content_id")
        if cid and cid not in existing_content_ids:
            issues.append(
                {
                    "item": "关键词失效",
                    "severity": "错误",
                    "detail": f"记录《{row.get('summary', '未命名')}》引用的 contentId "
                    f"{cid} 不存在",
                }
            )
    return issues


def check_pending_review_backlog(pending_rows: list, now: datetime = None) -> list:
    """检查待人工审核超过 14 天未处理。

    Args:
        pending_rows: [{'date': 'YYYY-MM-DD', 'status': '待审批', ...}, ...]
    """
    now = now or datetime.now()
    issues = []
    for row in pending_rows:
        if row.get("status") != "待审批":
            continue
        date = _parse_date(row.get("date"))
        if date and now - date > timedelta(days=BACKLOG_DAYS):
            issues.append(
                {
                    "item": "待审核积压",
                    "severity": "警告",
                    "detail": f"《{row.get('content_summary', '未命名')}》自 "
                    f"{row.get('date')} 起待审批已超过 {BACKLOG_DAYS} 天",
                }
            )
    return issues


def check_coverage_gap(coverage_rows: list, now: datetime = None) -> list:
    """检查 02-05 目录下"待补充项"是否超过 60 天未处理。

    Args:
        coverage_rows: [{'date': 'YYYY-MM-DD', 'status': '待补充', ...}, ...]
    """
    now = now or datetime.now()
    issues = []
    for row in coverage_rows:
        if row.get("status") != "待补充":
            continue
        date = _parse_date(row.get("date"))
        if date and now - date > timedelta(days=COVERAGE_STALE_DAYS):
            issues.append(
                {
                    "item": "覆盖率",
                    "severity": "警告",
                    "detail": f"《{row.get('summary', '未命名')}》待补充状态已超过 "
                    f"{COVERAGE_STALE_DAYS} 天",
                }
            )
    return issues


def check_redundancy(scenes: list) -> list:
    """粗粒度冗余检测：经验沉淀 / 踩坑记录中出现完全相同的 scene 文本。

    仅做字符串完全匹配的冗余检测（不做语义级矛盾检测，参见设计文档决策 4）。
    """
    seen = {}
    issues = []
    for scene in scenes:
        seen[scene] = seen.get(scene, 0) + 1
    for scene, cnt in seen.items():
        if cnt > 1:
            issues.append(
                {
                    "item": "冗余检测",
                    "severity": "警告",
                    "detail": f"场景「{scene}」在索引表中出现 {cnt} 次，可能是重复记录",
                }
            )
    return issues


def main(
    version_log_rows: list,
    existing_content_ids: set,
    pending_rows: list,
    coverage_rows: list,
    experience_scenes: list,
    now: datetime = None,
) -> dict:
    """
    汇总所有检查项，生成巡检报告。

    Returns:
        {
            'success': True,
            'report_summary': str,          # 一句话摘要（供学习日志 task_summary 使用）
            'report_detail': str,           # 详细报告（供学习日志 execution_review 使用）
            'issues': list,                 # 结构化问题列表
        }
    """
    now = now or datetime.now()
    issues = []
    issues += check_stale_version_log(version_log_rows, now)
    issues += check_dead_links(pending_rows + coverage_rows, existing_content_ids)
    issues += check_pending_review_backlog(pending_rows, now)
    issues += check_coverage_gap(coverage_rows, now)
    issues += check_redundancy(experience_scenes)

    error_count = sum(1 for i in issues if i["severity"] == "错误")
    warning_count = sum(1 for i in issues if i["severity"] == "警告")

    lines = [f"- 【{i['severity']}】{i['item']}：{i['detail']}" for i in issues]
    report_detail = "\n".join(lines) if lines else "未发现问题，知识库状态健康。"

    return {
        "success": True,
        "report_summary": f"知识库巡检：发现 {error_count} 个错误、{warning_count} 个警告",
        "report_detail": report_detail,
        "issues": issues,
    }


if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        payload = json.loads(sys.argv[1])
        print(json.dumps(main(**payload), ensure_ascii=False, indent=2))
    else:
        demo = main(
            version_log_rows=[{"date": "2026-07-01"}],
            existing_content_ids={"2780767955", "2781086741"},
            pending_rows=[
                {"date": "2026-07-20", "status": "待审批", "content_summary": "示例条目"}
            ],
            coverage_rows=[],
            experience_scenes=["学城文档批量追加写入", "学城文档批量追加写入"],
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2))
