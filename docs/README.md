# LingCat Knowledge Gardener 说明文档

灵猫知识库自治维护工具（Skill）。让 Agent 在执行任务的过程中，把自己的
学习反思、经验总结、踩过的坑、流程改进建议，自动沉淀进学城知识库，
并支持在人工审批后把成熟内容"转正"进权威业务目录。

本文档面向想要理解/使用/维护这个 skill 的人类读者，回答三个问题：
**它是什么、为什么这么设计、怎么用**。

- 完整设计动机与选型过程见 `设计文档v1.0.md`
- 完整接口定义与代码规范见 `实施文档.md`
- Agent 实际运行时读取的入口是仓库根目录的 `SKILL.md`

---

## 一、这个 Skill 是什么

### 1.1 一句话定位

Agent 在执行审计/分析等任务时，通常会积累经验、踩坑、发现流程问题。
这个 skill 让 Agent 能够**自主**把这些内容写进学城知识库的专属区域
（`06-Agent自建知识`），而不是每次都口头汇报完就忘记。

### 1.2 解决的核心问题

| 没有这个 skill 时 | 有了这个 skill 之后 |
|---|---|
| Agent 的经验只存在于单次会话里，会话结束就丢失 | 经验持久化到学城，跨会话、跨用户可复用 |
| Agent 想写知识库时，格式全靠临场发挥，质量参差不齐 | 统一走 Jinja2 模板渲染，格式和结构强制一致 |
| Agent 一旦能写知识库，容易失控地改动团队依赖的权威内容 | 严格读写分离：Agent 只能自由写"草稿区"，写"权威区"必须经人工审批 |
| "优化建议"和"内容转正"两件事容易被混为一谈，审批链路搞乱 | 两条通道在代码层面强制隔离，互不触发对方的后续动作 |

### 1.3 五个子能力

| 能力 | 触发时机 | 是否需要人工确认 |
|---|---|---|
| 📝 学习日志 | 每次任务结束后 | 无需 |
| ⚠️ 踩坑记录 | 遇到错误/异常时 | 无需 |
| 🧪 经验沉淀 | Agent 主观判断某操作模式已反复验证有效（无自动计数） | 需要（Agent 建议，用户确认后才写） |
| 💡 优化建议 | 发现某个流程/规范可以改进 | 需要（写入后还需人工审批才能落地） |
| 🔖 待人工审核 | Agent 认为某条知识已验证充分，值得转正进业务目录 | 需要（写入后需人工审批才能触发迁移） |

---

## 二、核心设计原理

### 2.1 原理一：读写分离，草稿区与权威区隔离

学城知识库分成两类目录：

```
01～05 业务目录          ← 团队依赖的权威知识，人工维护，Agent 严格只读
06-Agent自建知识          ← Agent 的"草稿本"，可以自由读写、允许试错
    ├── [01]学习日志
    ├── [02]经验沉淀
    ├── [03]踩坑记录
    ├── [04]优化建议
    └── [05]待人工审核     ← 唯一能"渗透"进业务目录的入口，且必须先经人工审批
```

**为什么这么设计**：业务目录是团队协作依赖的权威知识源，如果 Agent 能直接改写，
一旦产生幻觉或错误推断，会直接污染大家依赖的内容，还难以追溯是谁改的、为什么改的。
把 Agent 的写入权限限制在"草稿区"，即使写错了，影响范围也仅限于 06 目录内，
不会波及权威内容。想要转正必须走 `[05]待人工审核 → 人工确认 → migrate_to_business.py`
这一条唯一路径。

### 2.2 原理二：两条独立的审批通道，不能混用

这是最容易被误解、也是本 skill 明确用代码强制隔离的一点：

| 通道 | 审批对象 | 通过后做什么 |
|---|---|---|
| **优化建议**（`propose_optimization.py`） | "以后流程应该怎么做"（做法/规范层面） | 由人工手动去修改对应 SOP/规范文档，**不会**触发迁移脚本 |
| **待人工审核**（`write_pending_review.py`） | "这条已验证的知识内容该不该固化进业务目录" | 触发 `migrate_to_business.py`，把内容从 06 迁移到 01-05 |

如果把这两者混为一谈，会导致 `migrate_to_business.py` 误读优化建议里的自由文本
当作迁移目标，产生错误的业务目录变更。所以 `migrate_to_business.py` 的代码里
硬编码了校验逻辑：**只认 `[05]待人工审核` 里状态为"已审批"的条目，其他一律拒绝**
（见 `scripts/migrate_to_business.py` 的 `assert_approved()`）。

### 2.3 原理三：索引表 + 详情章节的复合文档结构

06 目录下 4 个文档（学习日志/经验沉淀/踩坑记录/优化建议）不是简单的一张表，
而是"索引表 + 详情章节"的复合结构：

```
文档结构示意：
┌─────────────────────────────────┐
│ 索引表（短字段，快速扫描定位）      │
│ | 日期 | 场景摘要 | 状态 |         │
│ | 8-18 | XX报错   | 已解决 |       │  ← 每次写入在此追加一行
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 详情记录（长字段，完整内容）        │
│ ## 8-18 | XX报错                 │
│ **错误信息**：（完整堆栈代码块）    │  ← 每次写入在此追加一个章节
│ **原因分析**：...                 │
│ **解决方案**：...                 │
└─────────────────────────────────┘
```

**为什么不用纯表格**：踩坑记录的错误堆栈、优化建议的风险评估都是长文本/多行内容，
学城表格单元格很窄（历史遗留 `colwidth=68`），硬塞长文本会导致阅读体验极差。

**为什么不用纯章节**：如果全篇都是 `## 标题` 章节，历史记录一多，翻页扫描
就找不到重点，失去了表格"一眼看全貌"的优势。

所以采用复合结构：**索引表**放短字段做快速定位，**详情章节**放长字段承载完整内容。
两者通过完全相同的标题文字关联（例如 `## 2026-08-18 | XX报错` 必须与索引表
对应行的场景描述文字一致）——因为学城不支持锚点跳转，只能靠文字匹配定位。

唯一例外是 `[05]待人工审核`：它的字段全部短小（日期/概要/目标目录/状态），
不需要详情章节，只有一张纯索引表。

### 2.4 原理四：Script 只管数据，Agent 才是真正的执行者

这是贯穿整个代码库的架构原则：

```
scripts/write_*.py
    ↓ 调用
lib/writer.py（KnowledgeWriter）
    ↓ 内部完成
1. 质量自检（quality_check）—— 检查必填字段是否为空、日期格式是否正确
2. 模板渲染（render_entry）—— 用 Jinja2 同时渲染出 row（索引行）+ detail（详情章节）
    ↓ 返回
{'success': True, 'content_id': ..., 'row': ..., 'detail': ..., 'message': ...}
    ↓ Agent 拿到这个结果后，自己去做
1. oa-skills citadel getDocumentXml  —— 拉取当前文档
2. 本地修改 XML —— 把 row 插进索引表，把 detail 插进详情章节
3. oa-skills citadel updateDocumentByXml —— 回写文档
```

**为什么 Script 不直接调用学城 API**：Script 只是一段纯函数式的数据处理逻辑
（拼字符串、判断字段是否为空），不涉及任何网络请求、不涉及 XML 解析和节点操作。
真正与学城交互、处理 XML 结构、保证 `nodeId` 不丢失等复杂操作，全部交给 Agent
借助 `oa-skills citadel` CLI 完成。这样 Script 可以脱离网络环境独立测试
（每个 Script 文件末尾都带了 `if __name__ == "__main__"` 的 demo，可以直接
`python scripts/write_learning_log.py` 跑起来看渲染结果），也避免了在 Script
里重复实现一遍复杂的 XML 拼接逻辑。

---

## 三、目录结构与文件职责

```
LingCat-Knowledge-Gardener/
├── SKILL.md                       # Agent 实际读取的入口：触发条件 + 路由决策树 + 用法速查
├── requirements.txt                # 唯一依赖：jinja2
│
├── lib/                             # 公共库（不涉及学城网络交互）
│   ├── content_ids.py               # 5 个目标文档的真实 contentId 常量
│   ├── writer.py                    # KnowledgeWriter：render_entry（渲染） + quality_check（自检）
│   └── jinja2_templates.py          # 独立的模板加载器（供 writer.py 复用，也可单独测试）
│
├── scripts/                         # 每个脚本对应 SKILL.md 路由决策树里的一个分支
│   ├── write_learning_log.py        # 写学习日志
│   ├── write_pitfall.py             # 写踩坑记录
│   ├── write_experience.py          # 写经验沉淀（手动触发）
│   ├── propose_optimization.py      # 提优化建议（手动触发，不转正）
│   ├── write_pending_review.py      # 提交内容转正申请（手动触发）
│   ├── health_check.py              # 知识库健康度巡检（不走 writer.py）
│   └── migrate_to_business.py       # 待审核 → 业务目录迁移（不走 writer.py，含安全拦截）
│
├── assets/templates/                 # Jinja2 模板，一个文档对应一对 row/detail（待审核只有 row）
│   ├── learning-log-row.j2 / learning-log-detail.j2
│   ├── pitfall-row.j2 / pitfall-detail.j2
│   ├── experience-row.j2 / experience-detail.j2
│   ├── optimization-row.j2 / optimization-detail.j2
│   └── pending-review-row.j2
│
├── references/                       # Agent 按需读取的参考文档（不会一次性全部塞进上下文）
│   ├── kb-structure.md               # 知识库六大目录定位、读写权限矩阵
│   ├── writing-rules.md              # 内容格式规范、学城 XML 约束、质量红线
│   ├── quality-checklist.md          # 写入前质量自检清单
│   └── approval-workflow.md          # 两条审批通道的详细流程和状态取值
│
└── docs/                             # 面向人类的设计文档（非 Agent 运行时读取）
    ├── README.md                     # 本文档
    ├── 设计文档v1.0.md                # 完整设计动机、选型对比、版本演进记录
    └── 实施文档.md                    # 完整接口定义、代码示例、开发阶段划分
```

---

## 四、怎么用

### 4.1 作为 Agent 技能使用（最终形态）

正常情况下，你不需要手动调用任何脚本——灵猫 Agent 会在合适的时机自动触发：

- 每次完成一个任务后，Agent 会主动调用 `write_learning_log.py` 记录反思
- 遇到报错并解决后，Agent 会主动调用 `write_pitfall.py` 记录踩坑
- 当 Agent 觉得某个操作模式已经验证多次、值得沉淀为经验时，会先跟你确认，
  你同意后才会调用 `write_experience.py`
- 当 Agent 发现某个流程可以优化，或某条自建知识值得转正进业务目录时，
  同样会先跟你确认，走 `propose_optimization.py` 或 `write_pending_review.py`

你能感知到的交互，通常是 Agent 汇报"已将本次排查过程写入学习日志"，
或者在写经验/提建议前询问你"要不要把这个操作沉淀成经验"。

### 4.2 人工审批环节（你需要做什么）

当 Agent 提交了「优化建议」或「待人工审核」条目后，需要你在学城文档里手动处理：

**优化建议**（`[04]优化建议`，contentId `2781276182`）：
- 打开文档，找到状态为"待审批"的行
- 决定是否采纳，如果采纳，**由你自己**去修改对应的 SOP/规范文档
  （这一步不会自动化，因为改的是"做法"，需要人工判断）
- 把索引表该行状态 + 详情章节里的状态/审批人字段都改掉（两处必须同步）

**待人工审核**（`[05]待人工审核`，contentId `2781426045`）：
- 打开文档，找到状态为"待审批"的行
- 确认这条知识内容确实值得转正后，把该行状态改为"**已审批**"
  （这个字符串是硬编码校验值，见 `scripts/migrate_to_business.py`）
- 告诉 Agent"可以合并了"，Agent 会调用 `migrate_to_business.py` 完成迁移，
  迁移后源条目状态会自动更新为"已合并至 XX"，源文档不会被删除

### 4.3 作为开发者独立测试某个脚本

每个 `scripts/*.py` 都可以脱离 Agent 环境直接用 Python 运行，用于验证模板渲染
是否符合预期：

```powershell
cd LingCat-Knowledge-Gardener
pip install -r requirements.txt

# 不带参数直接跑，会执行脚本内置的 demo 数据
python scripts\write_learning_log.py

# 带一个 JSON 字符串参数，可以自定义输入
python scripts\write_pitfall.py '{"scene": "xxx", "error_msg": "xxx", "root_cause": "xxx", "solution": "xxx", "prevention": "xxx"}'
```

> **关于中文乱码**：脚本本身全程使用 UTF-8（Jinja2 模板加载、JSON 输出均未指定
> 过非 UTF-8 编码），Agent 的实际运行环境是 Linux，终端默认就是 UTF-8 locale，
> 不会出现乱码。只有在 **Windows PowerShell 本地手动测试**时，会因为终端默认
> 代码页是 GBK 而显示乱码，这纯粹是本地终端显示问题，加一行
> `$env:PYTHONIOENCODING="utf-8"` 即可正常显示，与脚本代码无关，Linux 环境
> 下不需要做任何处理。

### 4.4 作为维护者修改模板或新增字段

1. 想改某个文档的格式，先改对应的 `assets/templates/{doc_key}-row.j2` /
   `{doc_key}-detail.j2`，两个文件是一一对应关系
2. 如果新增了字段，记得同步：
   - 对应 `scripts/write_*.py` 的 `main()` 函数签名和 `context` 字典
   - 如果这个字段是必填项，去 `lib/writer.py` 的 `quality_check()` 里加校验
   - 去 `references/writing-rules.md` 补充格式说明
3. 改完用 4.3 节的方式跑一遍脚本，确认渲染结果符合预期
4. **不要**去改 `lib/content_ids.py` 里的 contentId——这些是线上真实文档的
   固定值，改错会导致写入到错误的文档

---

## 五、安全边界（明确不做的事）

- **不直接改写业务目录（01-05）**：唯一入口是 `migrate_to_business.py`，
  且强制要求源条目状态为"已审批"，否则代码里直接拒绝执行
- **不会在没有确认的情况下写经验/提建议/申请转正**：`write_experience.py`、
  `propose_optimization.py`、`write_pending_review.py` 都要求人工先确认
- **不做语义级矛盾检测**：`health_check.py` 目前只做字符串完全匹配的冗余检测，
  更复杂的语义矛盾识别复杂度过高、收益不明确，留到后续版本再评估
- **不用简化 Markdown 直接回写文档**：学城的 `getSimpleMarkdown` 只是只读视图，
  所有写入必须走 `getDocumentXml → 改 XML → updateDocumentByXml` 的完整路径，
  保证不丢失原有的 `nodeId` 和文档结构

---

## 六、常见问题

**Q：为什么 Script 里不直接调用学城的接口把内容写进去？**
A：见 2.4 节。简单说就是"数据处理"和"网络交互"职责分离，Script 保持纯粹、
可脱离网络独立测试，复杂的 XML 操作交给 Agent 借助 citadel CLI 完成。

**Q：我能不能让 Agent 自动帮我审批优化建议？**
A：不能，这是硬性设计，审批环节必须有人工介入，否则失去了防止 Agent 幻觉
污染权威知识的意义。

**Q：经验沉淀里，同一个场景写了两次会怎样？**
A：`write_experience.py` 的设计是：如果 `scene` 在索引表中已存在，Agent 应该
只更新该行的验证次数（`count` 列），不重复创建新的详情章节。这个判断依赖
Agent 先读取当前文档内容做比对，脚本本身不做这个判断（脚本看不到线上文档）。

**Q：健康巡检发现的问题会自动修复吗？**
A：不会，`health_check.py` 只负责生成巡检报告并写入学习日志，具体问题
（内容过期、冗余记录、待审核积压等）仍需人工或后续任务处理。
