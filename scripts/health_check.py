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

DEFAULT_FACADE_THRESHOLD = 5  # C3 域门面文档数阈值（可配 3~8）

# C1 悬挂节点检查的治理文档白名单：索引体系自身的文档，不要求在索引C 登记。
# 注意：placeholder 占位文档不在此列——它们已在索引C 登记（status=placeholder），
# 天然不命中 C1，无需白名单豁免。
GOVERNANCE_WHITELIST = frozenset({
    "2775934808",  # 知识库根文档
    "2781633447",  # 00-知识库元信息 正文
    "2787700515",  # 索引A
    "2787068506",  # 索引B
    "2787258250",  # 索引C
    "2786789270",  # 变更日志
})

# C3 域门面检查不统计的治理目录（一级目录名）：00/06 的子树规模是设计固定的，
# 不存在“膨胀失控”风险。豁免后 C3 只关注会自然生长的业务目录。
# 注意：仅影响 C3 统计，C1/C2 对这两个目录的漂移监控不受影响。
GOVERNANCE_DIRS = frozenset({
    "00-知识库元信息",
    "06-Agent自建知识",
})


def _normalize_path(path) -> str:
    """规范化为 '一级目录/子目录/...' 格式（不含文档名）。

    只做最保守的处理：统一分隔符、去空白、去空段，不做大小写/全半角转换。
    """
    if not path:
        return ""
    parts = [p.strip() for p in str(path).replace("\\", "/").split("/")]
    return "/".join(p for p in parts if p)


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


def check_hanging_nodes(tree_docs: list, index_c_docs: list,
                        whitelist: set = None) -> list:
    """C1 悬挂节点：线上目录树存在、但索引C 未登记的文档。

    Args:
        tree_docs: [{'contentId':..., 'title':..., 'path': '01-xxx/子目录'}, ...]
            线上目录树全量遍历结果，path 为所在目录链（不含文档名）。
        index_c_docs: [{'contentId':..., 'path':...}, ...] 索引C 登记数据。
        whitelist: 不参与告警的 contentId 集合，缺省用 GOVERNANCE_WHITELIST。

    Returns:
        [{'contentId':..., 'title':..., 'path':..., 'suggestion':...}, ...]
    """
    whitelist = GOVERNANCE_WHITELIST if whitelist is None else {str(c) for c in whitelist}
    registered = {str(d.get("contentId")) for d in index_c_docs}
    hanging = []
    for doc in tree_docs:
        cid = str(doc.get("contentId"))
        if cid in registered or cid in whitelist:
            continue
        hanging.append({
            "contentId": cid,
            "title": doc.get("title", "未命名"),
            "path": _normalize_path(doc.get("path")),
            "suggestion": "建议走三步走补登记：①索引C 补录该文档 ②重渲染索引A/B "
                          "③变更日志追加一行",
        })
    return hanging


def check_path_mismatch(tree_docs: list, index_c_docs: list) -> list:
    """C2 path 失配：索引C 记录路径与文档实际所在目录链不一致。

    只比对两边都存在的文档（索引C 与线上目录树的交集）——线上有而索引C
    没有的归 C1 管，索引C 有而线上没有的归死链检查管，这里不重复报告。

    Returns:
        [{'contentId':..., 'title':..., 'index_path':..., 'actual_path':...,
          'suggestion':...}, ...]
    """
    index_paths = {
        str(d.get("contentId")): _normalize_path(d.get("path")) for d in index_c_docs
    }
    mismatches = []
    for doc in tree_docs:
        cid = str(doc.get("contentId"))
        if cid not in index_paths:
            continue
        actual = _normalize_path(doc.get("path"))
        if index_paths[cid] != actual:
            mismatches.append({
                "contentId": cid,
                "title": doc.get("title", "未命名"),
                "index_path": index_paths[cid],
                "actual_path": actual,
                "suggestion": "建议更新索引C 中该文档的 path 并重渲染索引A/B，"
                              "变更日志留痕",
            })
    return mismatches


def check_facade_candidates(tree_docs: list, index_c_docs: list,
                            threshold: int = DEFAULT_FACADE_THRESHOLD) -> list:
    """C3 域门面阈值：子树文档数 ≥ threshold 且尚未建域门面导读页。

    门面判定只认索引C 里的显式 is_facade 字段（缺省 False），不做标题猜测；
    门面的 path 指向它所覆盖的域根。每个文档计入其目录链上的所有祖先子树，
    根级文档（path 为空）不属于任何域，跳过；治理目录（GOVERNANCE_DIRS）
    下的文档不参与统计。

    Returns:
        [{'path':..., 'doc_count':..., 'suggestion':...}, ...] 按 path 排序
    """
    facade_subtrees = {
        _normalize_path(d.get("path")) for d in index_c_docs if d.get("is_facade")
    }
    counts = {}
    for doc in tree_docs:
        path = _normalize_path(doc.get("path"))
        if not path:
            continue
        parts = path.split("/")
        if parts[0] in GOVERNANCE_DIRS:
            continue  # 治理目录（00/06）规模固定，不参与域膨胀统计
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            counts[prefix] = counts.get(prefix, 0) + 1
    return [
        {
            "path": path,
            "doc_count": cnt,
            "suggestion": "建议经人工确认后按 00 维护规则第七条建域内导读页",
        }
        for path, cnt in sorted(counts.items())
        if cnt >= threshold and path not in facade_subtrees
    ]


def main(
    version_log_rows: list,
    existing_content_ids: set,
    pending_rows: list,
    coverage_rows: list,
    experience_scenes: list,
    now: datetime = None,
    tree_docs: list = None,
    index_c_docs: list = None,
    facade_threshold: int = DEFAULT_FACADE_THRESHOLD,
    whitelist: set = None,
) -> dict:
    """
    汇总所有检查项，生成巡检报告。

    Args:
        （前五个参数为现有内容健康检查，语义不变）
        tree_docs: 可选，线上目录树全量遍历结果
            [{'contentId':..., 'title':..., 'path': '01-xxx/子目录'}, ...]
        index_c_docs: 可选，索引C 登记数据
            [{'contentId':..., 'path':..., 'is_facade': bool（缺省 False）}, ...]
        facade_threshold: C3 域门面文档数阈值，默认 5（可配 3~8）
        whitelist: C1 白名单 contentId 集合，缺省为 6 个治理文档

        tree_docs 与 index_c_docs 同时传入时才启用 C1/C2/C3 结构一致性检查，
        缺省时行为与旧版本完全一致。

    Returns:
        {
            'success': True,
            'report_summary': str,          # 一句话摘要（供学习日志 task_summary 使用）
            'report_detail': str,           # 详细报告（供学习日志 execution_review 使用）
            'issues': list,                 # 结构化问题列表
            'structure_check': {            # 仅结构检查启用时存在
                'hanging_nodes': list,      # C1 悬挂节点
                'path_mismatch': list,      # C2 path 失配
                'facade_candidates': list,  # C3 域门面建议
            },
        }
    """
    now = now or datetime.now()
    issues = []
    issues += check_stale_version_log(version_log_rows, now)
    issues += check_dead_links(pending_rows + coverage_rows, existing_content_ids)
    issues += check_pending_review_backlog(pending_rows, now)
    issues += check_coverage_gap(coverage_rows, now)
    issues += check_redundancy(experience_scenes)

    structure_check = None
    if tree_docs is not None and index_c_docs is not None:
        hanging_nodes = check_hanging_nodes(tree_docs, index_c_docs, whitelist)
        path_mismatches = check_path_mismatch(tree_docs, index_c_docs)
        facade_candidates = check_facade_candidates(
            tree_docs, index_c_docs, facade_threshold
        )
        for h in hanging_nodes:
            issues.append({
                "item": "悬挂节点",
                "severity": "错误",
                "detail": f"文档《{h['title']}》(contentId {h['contentId']}) 实际位于 "
                          f"「{h['path'] or '根目录'}」，但未在索引C 登记。"
                          f"{h['suggestion']}",
            })
        for m in path_mismatches:
            issues.append({
                "item": "path失配",
                "severity": "错误",
                "detail": f"文档《{m['title']}》(contentId {m['contentId']}) 索引C "
                          f"记录路径为「{m['index_path'] or '根目录'}」，实际路径为 "
                          f"「{m['actual_path'] or '根目录'}」。{m['suggestion']}",
            })
        for fc in facade_candidates:
            issues.append({
                "item": "域门面建议",
                "severity": "警告",
                "detail": f"子树「{fc['path']}」已有 {fc['doc_count']} 篇文档（阈值 "
                          f"{facade_threshold}），但尚未建域门面导读页。"
                          f"{fc['suggestion']}",
            })
        structure_check = {
            "hanging_nodes": hanging_nodes,
            "path_mismatch": path_mismatches,
            "facade_candidates": facade_candidates,
        }

    error_count = sum(1 for i in issues if i["severity"] == "错误")
    warning_count = sum(1 for i in issues if i["severity"] == "警告")

    lines = [f"- 【{i['severity']}】{i['item']}：{i['detail']}" for i in issues]
    report_detail = "\n".join(lines) if lines else "未发现问题，知识库状态健康。"

    result = {
        "success": True,
        "report_summary": f"知识库巡检：发现 {error_count} 个错误、{warning_count} 个警告",
        "report_detail": report_detail,
        "issues": issues,
    }
    if structure_check is not None:
        result["structure_check"] = structure_check
    return result


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
