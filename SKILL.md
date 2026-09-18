---
name: lingcat-knowledge-gardener
description: 灵猫知识库自治维护工具。用于Agent自主更新学城知识库中的自建知识目录（06-Agent自建知识），包括学习日志、经验沉淀、踩坑记录、优化建议和待人工审核。触发条件：1) Agent完成审计任务后需要记录反思；2) Agent遇到错误或异常需要记录踩坑；3) Agent发现可优化的流程或规范；4) 定期巡检知识库健康度；5) 积累足够经验后提出内容转正申请。不触发：直接修改业务目录（01-05）；不触发：用户主动咨询知识库使用方式（那是00-知识库元信息的活）。

metadata:
  skillhub.creator: "sunhaobo05"
  skillhub.updater: "sunhaobo05"
  skillhub.version: "V2.2.0"
---

# LingCat Knowledge Gardener

灵猫知识库自治维护工具。核心原则：**Script 是工具，Agent 是指挥者**——
Script 只负责构造数据、质量自检、模板渲染，真正的学城读写操作
（`getDocumentXml` → 修改 XML → `updateDocumentByXml`）全部由 Agent
调用 `oa-skills citadel` CLI 完成。

## 核心理念（务必先理解，再动手）

- **三不原则**：不编数据、不跳步、不静默覆盖
- **读写分离**：Agent 可自由读写 `06-Agent自建知识` 目录；业务目录（01-05）
  严格只读，进入业务目录必须经过人工审批
- **两条独立审批通道**：「优化建议」改的是流程/规范；「待人工审核」改的是
  某条知识内容要不要转正。两者互不触发对方的后续动作，详见
  `references/approval-workflow.md`

## 路由决策树

```
用户指令 / 事件触发
    ↓
判断意图：
├── "写学习日志" / 任务结束 ────→ scripts/write_learning_log.py
├── "写经验沉淀" / Agent判断某操作模式已多次验证有效（需用户确认）─→ scripts/write_experience.py
├── "写踩坑记录" / 遇到错误异常 ──→ scripts/write_pitfall.py
├── "提优化建议" / 发现流程可改进空间 ─→ scripts/propose_optimization.py
├── "提内容转正申请" / 内容已验证充分 ─→ scripts/write_pending_review.py
├── "巡检知识库" / 定时/手动触发 ─→ scripts/health_check.py
└── "合并到业务目录" / [05]待人工审核已人工确认通过 → scripts/migrate_to_business.py
```

> 经验沉淀和优化建议是**手动触发**：Agent 可以主动建议"要不要写一条经验/
> 提个优化建议"，但必须等用户确认后才真正调用脚本。原因见
> `docs/实施文档.md` 第七节决策 1。

## 目标文档 contentId（真实值，固定常量，见 `lib/content_ids.py`）

06-Agent自建知识（父目录 contentId：`2780936747`）下 5 个子文档已在线上
建好固定表结构，**只能对以下 5 个 contentId 做追加写入，不得新建同类文档**：

| 文档 | contentId 常量 | 结构 |
|------|-----------|------|
| [01]学习日志 | `LEARNING_LOG_CONTENT_ID` (2780767955) | 索引表（日期/任务类型/反思摘要）+ 详情章节 |
| [02]经验沉淀 | `EXPERIENCE_CONTENT_ID` (2781086741) | 索引表（场景/经验摘要/验证次数/状态）+ 详情章节 |
| [03]踩坑记录 | `PITFALL_CONTENT_ID` (2781216217) | 索引表（日期/踩坑场景/状态）+ 详情章节 |
| [04]优化建议 | `OPTIMIZATION_CONTENT_ID` (2781276182) | 索引表（日期/优化目标/状态）+ 详情章节 |
| [05]待人工审核 | `PENDING_REVIEW_CONTENT_ID` (2781426045) | 纯索引表（日期/内容概要/目标合并目录/状态），无详情章节 |

## 通用写入流程（除 `health_check.py` / `migrate_to_business.py` 外）

每个 `write_*.py` / `propose_optimization.py` 都遵循同一套流程：

1. **调用 Script**：传入业务参数，Script 内部完成质量自检 + Jinja2 模板渲染，
   返回 `{'success': True, 'content_id': ..., 'row': ..., 'detail': ..., 'message': ...}`
   （`[05]待人工审核` 的 `detail` 恒为 `None`）
   - 若 `success: False`，说明质量自检未通过，根据 `message` 补充信息后重试，
     不允许绕过检查强行写入
2. **拉取当前文档**：
   ```
   oa-skills citadel getDocumentXml --contentId <content_id> --output /tmp/km-doc.xml
   ```
3. **本地修改 XML（两处同步追加，缺一不可）**：
   - 定位「索引表」下的 `<table>`，在最后一个 `<tr>` 之后插入 `row` 对应的新 `<tr>`
   - 定位「详情记录」标题（`<h2>详情记录</h2>`）之后，在末尾追加 `detail`
     对应的 `<h2>`/`<p>` 等章节节点（`[05]待人工审核` 跳过此步）
   - 保留所有原有 `nodeId`；新增节点可省略 `nodeId`
4. **回写文档**：
   ```
   oa-skills citadel updateDocumentByXml --contentId <content_id> --file /tmp/km-doc.xml --step-version <stepVersion>
   ```
5. **更新知识库元信息版本日志**：追加一行到 00-知识库元信息 的版本日志表
   （遵循已有列顺序：版本/日期/变更内容/维护人，维护人列标注为 `Agent`）
6. **确认写入成功**，向用户报告结果

写入前必读：`references/writing-rules.md`（格式规范）+
`references/quality-checklist.md`（质量自检清单，人工判断部分）。

## 各子流程一览

| 子流程 | 触发条件 | 脚本 | 人工介入 |
|--------|----------|------|----------|
| 学习日志 | 每次任务结束 | `write_learning_log.py` | 无需 |
| 踩坑记录 | 遇到错误/异常 | `write_pitfall.py` | 无需 |
| 经验沉淀 | Agent 主观判断某模式已反复验证有效（Agent建议+用户确认） | `write_experience.py` | 定期review |
| 优化建议 | 经验+踩坑中发现流程改进点 | `propose_optimization.py` | 必须审批 |
| 待人工审核 | Agent 认为某条内容已验证充分，值得转正 | `write_pending_review.py` | 必须审批 |
| 健康巡检 | 定时（建议每周）/ 手动触发 | `health_check.py` | 定期review |
| 业务目录迁移 | `[05]待人工审核` 中条目被人工标记"已审批" | `migrate_to_business.py` | 前置校验+diff确认 |

> ⚠️ `migrate_to_business.py` 的唯一合法输入源是 `[05]待人工审核`，
> **不是** `[04]优化建议`。调用前脚本会自动校验目标条目状态是否为"已审批"，
> 状态不符会拒绝执行并返回原因。

## 各脚本用法速查

### write_learning_log.py

```python
main(
    task_type: str,          # 审计排查/数据分析/报告生成/系统操作
    task_summary: str,       # 任务概要（1-2句，同时作为索引行摘要）
    execution_review: str,   # 执行过程回顾
    good_points: list[str],  # 做得好的地方
    improvements: list[str], # 可改进的地方（没有也要写"暂无"）
    linked_docs: list[str] = None,
) -> dict
```

### write_pitfall.py

```python
main(
    scene: str,          # 错误场景（同时作为索引行摘要）
    error_msg: str,      # 原始报错，可多行，详情章节用代码块承载
    root_cause: str,
    solution: str,
    prevention: str,
    status: str = "已解决",
    high_frequency: bool = False,  # 同类错误已出现≥3次时传 True
    frequency: int = None,
) -> dict
```

### write_experience.py（手动触发）

```python
main(
    scene: str,            # 同时作为索引行摘要和详情章节标题
    summary: str,          # 一句话经验摘要（仅索引行）
    steps: list[str],
    why_works: str,
    conditions: list[str],
    source_logs: list[str],
    count: int = 1,        # 验证次数（人工/Agent 手动维护，不是自动统计，见下方说明）
    status: str = "验证中",
) -> dict
```

> 若 `scene` 在索引表中已存在，Agent 应只更新该行 `count` 列，
> 不要重复插入新的 `detail` 章节。

**关于 `count`（验证次数）的定位，避免和"触发写入"的判断混淆**：

- **触发写入经验**（要不要新增一条经验）和 **验证次数**（这条经验被复用了几次）
  是两件独立的事，不要混为一谈：
  - 触发写入：Agent 主观判断某模式已反复验证有效 → 建议用户 → 用户确认后才写，
    **不存在任何计数阈值**（历史上曾设计过"≥3次自动检测"，已在决策中明确取消，
    原因是 Agent 会话无状态、无法持久化计数，见 `docs/实施文档.md` 决策 1）
  - 验证次数：字段本身**没有被取消**，仍然保留在索引表里，用途是给人工 review
    提供一个"这条经验有多可信"的参考信号——只验证过 1 次的经验和验证过 5 次的
    经验，可信度显然不同，`write_pending_review.py` 提交转正申请时也会引用这个
    数字作为支撑依据（例如"已验证 5 次，建议转正"）
- `count` 的值**由 Agent 每次判断"这是同一个 scene 的重复验证"时手动 +1**，
  不是脚本自动统计出来的（脚本看不到线上文档，无法自己计数）。Agent 需要先
  `getDocumentXml` 读取当前索引表，对比 `scene` 文本是否已存在，若存在则把
  该行 `count` 读出来 +1 后整行替换，而不是调用 `write_experience.py` 生成
  新的 `row`/`detail`

### propose_optimization.py（手动触发）

```python
main(
    target: str,               # 优化目标（流程/规范，同时作为索引行摘要）
    current: str,
    proposed: str,
    expected_benefit: list[str],
    risk_assessment: str,
    evidence: list[str],
) -> dict
```

### write_pending_review.py（手动触发）

```python
main(
    content_summary: str,   # 要转正的知识点概要
    target_dir: str,        # 目标合并目录（01-05 中某一个）
    source_link: str = None,
) -> dict
```

### health_check.py

不走 `lib/writer.py`。Agent 先通过 citadel CLI 拉取各文档索引表数据并
解析为结构化列表，再传入 `main()` 获得巡检报告。报告**不写入学习日志**：
把返回的 `version_log_entry` 追加到 00-知识库元信息 的版本日志表
（一次巡检一行，列序沿用 版本/日期/变更内容/维护人，变更内容列出每个
问题的具体定位，如「巡检：1错误2警告，悬挂节点：《xxx》(contentId)；
待审核积压：《yyy》」，最多 5 条、超出写"等 N 处"），问题明细由 Agent
在会话内向用户报告。

```python
main(
    version_log_rows: list[dict],
    existing_content_ids: set,
    pending_rows: list[dict],
    coverage_rows: list[dict],
    experience_scenes: list[str],
    tree_docs: list[dict] = None,     # 可选：线上目录树全量遍历，传了才启用结构检查
    index_c_docs: list[dict] = None,  # 可选：索引C 登记数据（含显式 is_facade 字段）
    facade_threshold: int = 5,        # 可选：C3 域门面阈值（可配 3~8）
    whitelist: set = None,            # 可选：C1 白名单，缺省为 6 个治理文档 contentId
) -> dict
```

`tree_docs` 与 `index_c_docs` 同时传入时额外执行三项结构一致性检查
（C1 悬挂节点 / C2 path 失配 / C3 域门面阈值），返回 dict 中新增
`structure_check` section；不传则行为与旧版本完全一致。C3 统计时自动
豁免治理目录（`00-知识库元信息` / `06-Agent自建知识`，脚本内置常量
`GOVERNANCE_DIRS`），只关注业务目录的域膨胀；该豁免不影响 C1/C2。采集方式：Agent 用
`getChildContent` 从根 2775934808 递归遍历目录树得到 `tree_docs`，用
`getDocumentXml` 拉索引C（2787258250）解析 JSON 得到 `index_c_docs`。
脚本只报告、不自动修复，修复走三步走并需用户确认。

### migrate_to_business.py

不走 `lib/writer.py`，涉及跨文档操作。调用前必须先读取
`[05]待人工审核` 最新 XML 确认目标行状态：

```python
main(
    pending_row: dict,               # 待审核索引表中的一行（含 status 字段）
    source_content: str,             # 待迁移的完整内容
    target_existing_content: str = "",
) -> dict
```

返回结果包含 `diff_preview`（先展示给用户确认）、`source_status_update`
（源条目状态更新文本）、`version_log_entry`（版本日志新增行）。
`success: False` 表示审批状态不满足，禁止继续执行。

## 参考文档索引

- `references/kb-structure.md` —— 知识库六大目录的定位、读写权限矩阵
- `references/writing-rules.md` —— 内容格式规范、学城 XML 约束、质量红线
- `references/quality-checklist.md` —— 写入前质量自检清单
- `references/approval-workflow.md` —— 两条审批通道的详细流程和状态取值

## 学城 CLI 使用约定

所有学城交互都通过 `oa-skills citadel` CLI 完成，禁止使用 `getSimpleMarkdown`
的结果去创建或更新文档（那只是简化版只读视图）。完整命令参考见
`C:\Users\sunhaobo05\.catpaw\skills\skills-market\citadel\SKILL.md`。

## 不做的事情（明确边界）

- 不直接修改业务目录（01-05）的任何内容，唯一入口是 `migrate_to_business.py`
- 不在没有用户确认的情况下调用 `write_experience.py` / `propose_optimization.py` /
  `write_pending_review.py`（这三者都需要人工确认才触发）
- 不做语义级矛盾检测（`health_check.py` 目前只做字符串完全匹配的冗余检测，
  复杂度与当前收益不匹配，留到 v2.0）
- 不用 `<km-markdown>` 标签直接回写学城文档
