# LingCat Knowledge Gardener（灵猫知识库园丁）

灵猫知识库自治维护工具（CatPaw Skill），帮助 Agent 自主维护学城知识库中的
`06-Agent自建知识` 目录，包括学习日志、经验沉淀、踩坑记录、优化建议和待人工审核。

- 版本：V2.2.0
- 维护人：sunhaobo05

## 核心理念

**Script 是工具，Agent 是指挥者**：Script 只负责构造数据、质量自检、模板渲染；
真正的学城读写操作（`getDocumentXml` → 修改 XML → `updateDocumentByXml`）
全部由 Agent 调用 `oa-skills citadel` CLI 完成。

- **三不原则**：不编数据、不跳步、不静默覆盖
- **读写分离**：`06-Agent自建知识` 目录可自由读写；业务目录（01-05）严格只读，
  进入业务目录必须经过人工审批
- **两条独立审批通道**：「优化建议」改流程/规范；「待人工审核」决定知识内容
  是否转正，两者互不触发对方的后续动作

## 使用方式

本工具作为 CatPaw Skill 安装后，通过自然语言指令或事件触发使用，无需手动调用。
Agent 会根据路由决策树自动选择合适的脚本。

### 触发方式一览

| 你说什么 / 发生什么 | 执行的脚本 | 是否需要人工确认 |
|---------------------|-----------|------------------|
| "写学习日志" / 任务结束 | `scripts/write_learning_log.py` | 无需 |
| "写踩坑记录" / 遇到错误异常 | `scripts/write_pitfall.py` | 无需 |
| "写经验沉淀" / 某操作模式多次验证有效 | `scripts/write_experience.py` | 需用户确认后触发 |
| "提优化建议" / 发现流程可改进 | `scripts/propose_optimization.py` | 必须审批 |
| "提内容转正申请" / 内容验证充分 | `scripts/write_pending_review.py` | 必须审批 |
| "巡检知识库" / 定时（建议每周） | `scripts/health_check.py` | 定期 review |
| "合并到业务目录" / 待审核条目已审批 | `scripts/migrate_to_business.py` | 前置校验 + diff 确认 |

> 注意：经验沉淀、优化建议、内容转正为**手动触发**——Agent 可以主动建议，
> 但必须等用户确认后才真正调用脚本。

### 典型使用示例

```
# 任务结束后记录反思
"帮我写一条学习日志"

# 遇到报错时记录踩坑
"把刚才这个错误记到踩坑记录里"

# 每周例行巡检
"巡检一下知识库健康度"

# 把验证充分的内容申请转正
"把那条经验沉淀提交转正申请，目标合并到 01 目录"
```

### 通用写入流程（Agent 自动执行）

1. 调用对应 Script 完成质量自检 + 模板渲染（自检不通过会返回原因，补充后重试）
2. `oa-skills citadel getDocumentXml` 拉取当前文档
3. 本地修改 XML：索引表追加 `<tr>`，详情章节追加内容（两处同步，缺一不可）
4. `oa-skills citadel updateDocumentByXml` 回写文档
5. 更新 `00-知识库元信息` 的版本日志（维护人标注为 `Agent`）
6. 向用户确认写入成功

## 目标文档

`06-Agent自建知识`（父目录 contentId：`2780936747`）下 5 个固定子文档，
只能追加写入，不得新建同类文档：

| 文档 | 结构 |
|------|------|
| [01]学习日志 | 索引表 + 详情章节 |
| [02]经验沉淀 | 索引表（含验证次数/状态）+ 详情章节 |
| [03]踩坑记录 | 索引表 + 详情章节 |
| [04]优化建议 | 索引表 + 详情章节 |
| [05]待人工审核 | 纯索引表，无详情章节 |

## 目录结构

```
LingCat-Knowledge-Gardener/
├── SKILL.md                    # Skill 定义与完整使用说明
├── scripts/                    # 写入/巡检/迁移脚本（质量自检 + 模板渲染）
├── lib/                        # 公共库（content_ids、writer 等）
├── references/                 # 规范文档（写入规则、质量清单、审批流程、知识库结构）
├── assets/templates/           # Jinja2 渲染模板
└── docs/                       # 实施文档、用户手册等
```

## 明确边界（不做的事）

- 不直接修改业务目录（01-05），唯一入口是 `migrate_to_business.py`
- 不在没有用户确认的情况下写经验/提优化/提转正
- 不做语义级矛盾检测（当前仅字符串完全匹配的冗余检测）
- 不用 `<km-markdown>` 标签直接回写学城文档

## 更多参考

- `SKILL.md` —— 完整的脚本参数签名与路由决策树
- `references/writing-rules.md` —— 内容格式规范、学城 XML 约束
- `references/quality-checklist.md` —— 写入前质量自检清单
- `references/approval-workflow.md` —— 两条审批通道的详细流程
- `docs/用户使用手册.md` —— 面向用户的使用手册
