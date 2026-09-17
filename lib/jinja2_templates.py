"""
Jinja2 模板加载器。

命名规则：每个文档对应一对模板 —— `{doc_key}-row.j2`（索引行，渲染为
一行 Markdown 表格行，对应回传 XML 中的一个 <tr>）与 `{doc_key}-detail.j2`
（详情章节，渲染为 `## 标题` 开头的一个章节）。`pending-review` 只有 `-row.j2`。

`lib/writer.py` 的 `KnowledgeWriter.render_entry` 已经封装了本加载器的
典型用法，日常写入 Script 优先使用 `KnowledgeWriter`；本模块单独存在是
为了让模板加载逻辑可以脱离 `KnowledgeWriter` 独立测试和复用（如
health_check.py 需要读取模板做格式校验时）。
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class Jinja2TemplateLoader:
    def __init__(self):
        # 模板目录：assets/templates/
        self.template_dir = Path(__file__).parent.parent / "assets" / "templates"
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            keep_trailing_newline=True,
        )

    def load(self, template_name: str):
        """加载模板

        Args:
            template_name: 模板文件名（如 'learning-log-row.j2'）

        Returns:
            jinja2.Template 对象
        """
        try:
            return self.env.get_template(template_name)
        except TemplateNotFound as e:
            raise FileNotFoundError(f"模板不存在: {template_name}") from e

    def render(self, template_name: str, context: dict) -> str:
        """加载并渲染模板。"""
        return self.load(template_name).render(**context)
