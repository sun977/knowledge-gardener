# 写入前质量自检清单

每次调用 `scripts/write_*.py` / `scripts/propose_optimization.py` 之前，
Agent 必须逐项过一遍下面的清单。前两项由 `lib/writer.py` 的
`KnowledgeWriter.quality_check()` 自动校验，其余各项需 Agent 人工判断。

- [ ] **内容不为空**：所有必填字段都有实质内容，不是占位符或空字符串
- [ ] **日期格式正确**：`YYYY-MM-DD`（如 `2026-08-18`）
- [ ] **所有数值有来源标注**：涉及数字的结论必须能说清楚数字从哪来
- [ ] **相对性判断附带基线值**："下降了"必须写清楚"从 X 降到 Y，降幅 Z%"
- [ ] **与现有内容无矛盾**：写入前检查同一文档中是否已有相似记录（尤其是经验沉淀
      的 `scene` 去重、踩坑记录的高频坑识别）
- [ ] **格式符合模板规范**：索引行短字段、详情章节长字段，两者标题一致，参见
      `references/writing-rules.md`
- [ ] **链接可达性验证**：如果记录中包含 `linked_docs` / `source_logs` /
      `source_link` 等链接字段，确认链接格式正确（引用了真实存在的 contentId
      或 URL，而非编造）

## 自动校验部分（`KnowledgeWriter.quality_check`）

| content_type | 校验项 |
|--------------|--------|
| `learning_log` | `task_summary` 非空；`improvements` 至少 1 项 |
| `pitfall` | `scene` / `error_msg` / `solution` 非空 |
| `experience` | `scene` / `summary` 非空；`steps` 至少 1 项 |
| `optimization` | `target` / `proposed` / `risk_assessment` 非空 |
| `pending_review` | `content_summary` / `target_dir` 非空 |

自动校验只能兜底"字段为空"这类硬错误，**不能**替代人工对内容质量红线
（编造数据、无来源判断等）的判断。质量自检失败时，`writer.py` 会抛出
`QualityCheckError`，各 Script 会返回 `{'success': False, 'message': ..., 'retryable': True}`，
Agent 应据此提示用户补充信息后重试，不得绕过检查强行写入。
