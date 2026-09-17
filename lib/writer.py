"""
公共写入库：只负责「模板渲染」和「质量自检」，不包含任何学城交互逻辑。

学城操作（getDocumentXml → 修改 XML → updateDocumentByXml）全部由 Agent
调用 citadel CLI 完成。Script 是工具，Agent 是指挥者：Script 只管构造数据，
Agent 负责协调所有操作。
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

TEMPLATE_DIR = Path(__file__).parent.parent / "assets" / "templates"

# render_entry 中除 pending-review 外都有独立的 detail 模板
DOC_KEYS_WITHOUT_DETAIL = {"pending-review"}


class KnowledgeGardenerError(Exception):
    """基类错误"""


class WriterError(KnowledgeGardenerError):
    """写入错误"""

    def __init__(self, message, step=None):
        self.step = step  # 出错步骤（如 'render_entry'）
        super().__init__(f"{step}: {message}" if step else message)


class TemplateError(WriterError):
    """模板渲染错误"""


class QualityCheckError(WriterError):
    """质量自检失败"""


class ApiError(WriterError):
    """API 调用错误（预留：当前版本学城交互由 Agent 完成，Script 内不直接调用 API）"""

    def __init__(self, message, status_code=None):
        self.status_code = status_code
        super().__init__(message)


class KnowledgeWriter:
    def __init__(self):
        """初始化写入库（模板加载器）。"""
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            keep_trailing_newline=True,
        )

    def render_entry(self, doc_key: str, context: dict) -> dict:
        """
        渲染一条完整记录（索引行 + 详情章节）。

        Args:
            doc_key: 文档标识（'learning-log' / 'pitfall' / 'experience' /
                      'optimization' / 'pending-review'）
            context: 模板上下文变量（字典）

        Returns:
            {
                'row': 索引表新增的一行（Markdown 表格行字符串）,
                'detail': 详情章节内容（Markdown 字符串），pending-review 恒为 None
            }
        """
        try:
            row_template = self.env.get_template(f"{doc_key}-row.j2")
            row = row_template.render(**context)
        except TemplateNotFound as e:
            raise TemplateError(f"索引行模板不存在: {doc_key}-row.j2", step="render_entry") from e

        detail = None
        if doc_key not in DOC_KEYS_WITHOUT_DETAIL:
            try:
                detail_template = self.env.get_template(f"{doc_key}-detail.j2")
                detail = detail_template.render(**context)
            except TemplateNotFound as e:
                raise TemplateError(
                    f"详情章节模板不存在: {doc_key}-detail.j2", step="render_entry"
                ) from e

        return {"row": row, "detail": detail}

    def quality_check(self, content_type: str, context: dict) -> list:
        """
        质量自检（对应 references/quality-checklist.md 的机器可判定部分）。

        Returns:
            失败的检查项列表（空列表表示通过）
        """
        errors = []

        # 1. 日期格式检查（YYYY-MM-DD），pending-review 系列均带 date
        date = context.get("date", "")
        if date and (len(date) != 10 or date[4] != "-" or date[7] != "-"):
            errors.append("日期格式不正确，应为 YYYY-MM-DD")

        # 2. 按内容类型做特定检查
        if content_type == "learning_log":
            if not context.get("task_summary", "").strip():
                errors.append("task_summary 不能为空")
            improvements = context.get("improvements") or []
            if not improvements or all(not i.strip() for i in improvements):
                errors.append('improvements 至少列出 1 项（即使没有也要写"暂无"）')

        elif content_type == "pitfall":
            if not context.get("scene", "").strip():
                errors.append("scene 不能为空")
            if not context.get("error_msg", "").strip():
                errors.append("error_msg 不能为空")
            if not context.get("solution", "").strip():
                errors.append("solution 不能为空")

        elif content_type == "experience":
            if not context.get("scene", "").strip():
                errors.append("scene 不能为空")
            if not context.get("summary", "").strip():
                errors.append("summary 不能为空")
            steps = context.get("steps") or []
            if not steps:
                errors.append("steps 至少列出 1 项")

        elif content_type == "optimization":
            if not context.get("target", "").strip():
                errors.append("target 不能为空")
            if not context.get("proposed", "").strip():
                errors.append("proposed 不能为空")
            if not context.get("risk_assessment", "").strip():
                errors.append("risk_assessment 不能为空")

        elif content_type == "pending_review":
            if not context.get("content_summary", "").strip():
                errors.append("content_summary 不能为空")
            if not context.get("target_dir", "").strip():
                errors.append("target_dir 不能为空")

        return errors
