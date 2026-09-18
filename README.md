# LingCat Knowledge Gardener（灵猫知识库园丁）

灵猫知识库自治维护工具（CatPaw Skill）。让 Agent 在执行任务的过程中，把自己的
学习反思、经验总结、踩过的坑、流程改进建议，自动沉淀进学城知识库的专属区域
（`06-Agent自建知识`），支持在人工审批后把成熟内容"转正"进权威业务目录，
并周期性巡检知识库的结构一致性与内容健康度。

- 版本：V3.0.0
- 维护人：sunhaobo05

> 本文档面向人类读者，回答"它是什么、为什么这么设计、怎么用"。
> Agent 运行时实际读取的入口是 `SKILL.md`。

## 解决的核心问题

| 没有这个 skill 时 | 有了这个 skill 之后 |
|---|---|
| Agent 的经验只存在于单次会话里，会话结束就丢失 | 经验持久化到学城，跨会话、跨用户可复用 |
| Agent 想写知识库时，格式全靠临场发挥，质量参差不齐 | 统一走 Jinja2 模板渲染，格式和结构强制一致 |
| Agent 一旦能写知识库，容易失控地改动团队依赖的权威内容 | 严格读写分离：Agent 只能自由写"草稿区"，写"权威区"必须经人工审批 |
| "优化建议"和"内容转正"两件事容易被混为一谈，审批链路搞乱 | 两条通道在代码层面强制隔离，互不触发对方的后续动作 |
| 有人绕过"三步走"直接动目录树，索引C 与实际结构漂移无人察觉 | 巡检的结构一致性检查（C1/C2/C3）周期性兜底，漂移留痕到版本日志 |

## 核心理念

**Script 是工具，Agent 是指挥者**：Script 只负责构造数据、质量自检、模板渲染
（纯函数、不访问网络、可独立测试）；真正的学城读写操作
（`getDocumentXml` → 修改 XML → `updateDocumentByXml`）全部由 Agent
调用 `oa-skills citadel` CLI 完成。

- **三不原则**：不编数据、不跳步、不静默覆盖
- **读写分离**：`06-Agent自建知识` 可自由读写；业务目录（01-05）严格只读，
  进入业务目录必须经过人工审批
- **两条独立审批通道**：「优化建议」改流程/规范（人工手动落地）；「待人工审核」
  决定知识内容是否转正（审批后触发迁移脚本），两者互不触发对方的后续动作
- **索引表 + 详情章节复合结构**：索引表放短字段快速定位，详情章节放长文本
  承载完整内容（学城表格单元格窄，塞不下错误堆栈等多行内容）

## 触发方式一览

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

## 巡检说明（health_check.py）

巡检脚本**不走** `lib/writer.py`，保持"纯计算、不访问网络"：所有线上数据由
Agent 通过 citadel CLI 采集（`getChildContent` 遍历目录树、`getDocumentXml`
拉取各文档）并结构化后传入 `main()`。

**检查项**：

| 类别 | 检查项 | 严重级别 |
|------|--------|---------|
| 内容健康 | 版本日志过期（30 天）、死链、待审核积压（14 天）、待补充过期（60 天）、冗余场景 | 错误/警告 |
| 结构一致性 | C1 悬挂节点（线上有、索引C 未登记） | 错误 |
| 结构一致性 | C2 path 失配（索引C 记录路径与实际目录链不一致） | 错误 |
| 结构一致性 | C3 域门面阈值（业务子树 ≥5 篇且无导读页，阈值可配 3~8） | 警告（建议级） |

**关键规则**：

- C1 白名单缺省为 6 个治理文档（根、00 正文、索引A/B/C、变更日志）；
  placeholder 文档已入索引C，天然不命中 C1
- C3 自动豁免治理目录（`00-知识库元信息` / `06-Agent自建知识`），
  只关注业务目录的域膨胀；门面判定只认索引C 里显式 `is_facade` 字段
- **输出去向**：巡检结果**不写入学习日志**。Agent 把返回的
  `version_log_entry` 追加到 `00-知识库元信息` 的版本日志表（一次巡检一行，
  变更内容列出每个问题的具体定位，最多 5 条、超出写"等 N 处"），
  问题明细由 Agent 在会话内向用户报告
- **只报告、不自动修复**：C1/C2 漂移走"三步走"人工修复，C3 建议需人工确认

## 通用写入流程（Agent 自动执行）

适用于各 `write_*.py` / `propose_optimization.py`（巡检与迁移除外）：

1. 调用对应 Script 完成质量自检 + 模板渲染（自检不通过会返回原因，补充后重试）
2. `oa-skills citadel getDocumentXml` 拉取当前文档
3. 本地修改 XML：索引表追加 `<tr>`，详情章节追加内容（两处同步，缺一不可）
4. `oa-skills citadel updateDocumentByXml` 回写文档
5. 更新 `00-知识库元信息` 的版本日志（维护人标注为 `Agent`）
6. 向用户确认写入成功

## 目标文档

`06-Agent自建知识`（父目录 contentId：`2780936747`）下 5 个固定子文档，
只能追加写入，不得新建同类文档（真实 contentId 见 `lib/content_ids.py`）：

| 文档 | 结构 |
|------|------|
| [01]学习日志 | 索引表 + 详情章节 |
| [02]经验沉淀 | 索引表（含验证次数/状态）+ 详情章节 |
| [03]踩坑记录 | 索引表 + 详情章节 |
| [04]优化建议 | 索引表 + 详情章节 |
| [05]待人工审核 | 纯索引表，无详情章节 |

## 人工审批环节（你需要做什么）

**优化建议**（`[04]优化建议`，contentId `2781276182`）：

- 打开文档，找到状态为"待审批"的行
- 决定是否采纳，如果采纳，**由你自己**去修改对应的 SOP/规范文档
- 把索引表该行状态 + 详情章节里的状态/审批人字段都改掉（两处必须同步）

**待人工审核**（`[05]待人工审核`，contentId `2781426045`）：

- 打开文档，找到状态为"待审批"的行
- 确认内容值得转正后，把该行状态改为"**已审批**"
  （硬编码校验值，见 `scripts/migrate_to_business.py`）
- 告诉 Agent"可以合并了"，Agent 调用 `migrate_to_business.py` 完成迁移，
  迁移后源条目状态更新为"已合并至 XX"，源文档不会被删除

## 开发者独立测试

每个 `scripts/*.py` 都可以脱离 Agent 环境直接运行，验证渲染/计算结果：

```powershell
cd LingCat-Knowledge-Gardener
pip install -r requirements.txt

# 不带参数直接跑，执行脚本内置 demo 数据
python scripts\write_learning_log.py
python scripts\health_check.py

# 带一个 JSON 字符串参数，自定义输入
python scripts\write_pitfall.py '{"scene": "xxx", "error_msg": "xxx", "root_cause": "xxx", "solution": "xxx", "prevention": "xxx"}'
```

> **Windows 中文乱码**：脚本全程 UTF-8，仅在 Windows PowerShell 本地测试时
> 因终端默认 GBK 代码页显示乱码，加 `$env:PYTHONIOENCODING="utf-8"` 即可，
> 与脚本代码无关。

## 目录结构

```
LingCat-Knowledge-Gardener/
├── SKILL.md                       # Agent 实际读取的入口：触发条件 + 路由决策树 + 用法速查
├── README.md                      # 本文档
├── requirements.txt               # 唯一依赖：jinja2
│
├── lib/                           # 公共库（不涉及学城网络交互）
│   ├── content_ids.py             # 5 个目标文档的真实 contentId 常量
│   ├── writer.py                  # KnowledgeWriter：render_entry（渲染） + quality_check（自检）
│   └── jinja2_templates.py        # 独立的模板加载器
│
├── scripts/                       # 每个脚本对应路由决策树的一个分支
│   ├── write_learning_log.py      # 写学习日志
│   ├── write_pitfall.py           # 写踩坑记录
│   ├── write_experience.py        # 写经验沉淀（手动触发）
│   ├── propose_optimization.py    # 提优化建议（手动触发，不转正）
│   ├── write_pending_review.py    # 提交内容转正申请（手动触发）
│   ├── health_check.py            # 健康度 + 结构一致性巡检（不走 writer.py）
│   └── migrate_to_business.py     # 待审核 → 业务目录迁移（不走 writer.py，含安全拦截）
│
├── assets/templates/              # Jinja2 模板，一个文档对应一对 row/detail（待审核只有 row）
├── references/                    # Agent 按需读取的规范文档
│   ├── kb-structure.md            # 知识库六大目录定位、读写权限矩阵
│   ├── writing-rules.md           # 内容格式规范、学城 XML 约束、质量红线
│   ├── quality-checklist.md       # 写入前质量自检清单
│   └── approval-workflow.md       # 两条审批通道的详细流程和状态取值
│
└── docs/                          # 面向人类的过程文档（非 Agent 运行时读取）
    ├── 设计文档v1.0.md             # 完整设计动机、选型对比、版本演进记录
    ├── 实施文档.md                 # 完整接口定义、代码示例、开发阶段划分
    ├── 用户使用手册.md             # 面向用户的使用手册
    └── 优化文档-20260917.md        # R5 巡检增强需求说明
```

## 安全边界（明确不做的事）

- **不直接改写业务目录（01-05）**：唯一入口是 `migrate_to_business.py`，
  且强制要求源条目状态为"已审批"，否则代码里直接拒绝执行
- **不在没有确认的情况下写经验/提建议/申请转正**：`write_experience.py`、
  `propose_optimization.py`、`write_pending_review.py` 都要求人工先确认
- **不做语义级矛盾检测**：`health_check.py` 只做字符串完全匹配的冗余检测
- **不用 `<km-markdown>` 标签或 `getSimpleMarkdown` 结果回写文档**：
  所有写入必须走 `getDocumentXml → 改 XML → updateDocumentByXml` 完整路径，
  保证不丢失原有 `nodeId` 和文档结构

## 常见问题

**Q：为什么 Script 里不直接调用学城的接口把内容写进去？**
A："数据处理"和"网络交互"职责分离。Script 保持纯粹、可脱离网络独立测试，
复杂的 XML 操作交给 Agent 借助 citadel CLI 完成。

**Q：能不能让 Agent 自动帮我审批优化建议？**
A：不能，这是硬性设计。审批环节必须有人工介入，否则失去了防止 Agent 幻觉
污染权威知识的意义。

**Q：经验沉淀里，同一个场景写了两次会怎样？**
A：如果 `scene` 在索引表中已存在，Agent 应只更新该行的验证次数（`count` 列），
不重复创建详情章节。这个判断依赖 Agent 先读取当前文档做比对，脚本本身
不做判断（脚本看不到线上文档）。

**Q：巡检报告写到哪里？发现的问题会自动修复吗？**
A：巡检结果以 `version_log_entry` 形式追加到 `00-知识库元信息` 的版本日志表
（一次巡检一行，含问题定位），不再写入 [01]学习日志；问题明细由 Agent 在
会话内报告。不会自动修复——C1/C2 漂移走"三步走"人工修复，C3 建议和内容
健康问题需人工或后续任务处理。

## 更多参考

- `SKILL.md` —— 完整的脚本参数签名与路由决策树（Agent 运行时入口）
- `references/writing-rules.md` —— 内容格式规范、学城 XML 约束
- `references/quality-checklist.md` —— 写入前质量自检清单
- `references/approval-workflow.md` —— 两条审批通道的详细流程
- `docs/用户使用手册.md` —— 面向用户的使用手册
- `docs/优化文档-20260917.md` —— R5 结构一致性巡检需求说明
