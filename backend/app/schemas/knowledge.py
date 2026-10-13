"""M11 企业知识库请求/响应结构。"""

from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeDocIn(BaseModel):
    """沉淀一条知识文档。"""

    title: str = Field(..., min_length=1, max_length=200, description="文档标题")
    doc_type: str = Field(default="experience", description="experience/sop/insight/policy/manual")
    status: str = Field(default="published", description="draft/published/archived")
    content: Optional[str] = Field(default=None, description="正文内容")
    summary: Optional[str] = Field(default=None, description="摘要（供 Agent 快速引用）")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    scenario: Optional[str] = Field(default=None, max_length=200, description="适用场景")
    source: str = Field(default="manual", description="来源 manual/insight/learning/agent")
    author: str = Field(default="system", max_length=64, description="作者/沉淀者")


class KnowledgeDocPatch(BaseModel):
    """修改知识文档。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    doc_type: Optional[str] = Field(default=None, description="experience/sop/insight/policy/manual")
    status: Optional[str] = Field(default=None, description="draft/published/archived")
    content: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    tags: Optional[list[str]] = Field(default=None)
    scenario: Optional[str] = Field(default=None, max_length=200)


class KnowledgeQueryIn(BaseModel):
    """检索知识库（Agent 引用入口）。"""

    keyword: str = Field(default="", description="关键词（标题/正文/摘要/标签）")
    doc_type: Optional[str] = Field(default=None, description="限定类型")
    scenario: Optional[str] = Field(default=None, max_length=200, description="限定适用场景")
    limit: int = Field(default=5, ge=1, le=50, description="返回条数")


class KnowledgeRefIn(BaseModel):
    """登记一次知识引用（Agent/用户引用轨迹）。"""

    doc_ids: list[int] = Field(..., min_length=1, description="被引用文档 ID 列表")
    source: str = Field(default="agent", description="引用来源 agent/user/system/insight_center/decision_studio")
    ref_key: Optional[str] = Field(default=None, max_length=128, description="引用方标识")
    note: Optional[str] = Field(default=None, description="引用说明")


class KnowledgeBaseIn(BaseModel):
    """新建知识库。"""

    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(default=None, max_length=500, description="描述")
    config: Optional[dict] = Field(default=None, description="配置（top_k/模型/标签等）")


class KnowledgeBasePatch(BaseModel):
    """修改知识库配置。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    config: Optional[dict] = Field(default=None)
    status: Optional[str] = Field(default=None, description="active/disabled")


class KnowledgeAskIn(BaseModel):
    """知识库问答提问。"""

    question: str = Field(..., min_length=1, max_length=1000, description="问题")
    top_k: int = Field(default=5, ge=1, le=20, description="召回条数")


class KnowledgeAskOut(BaseModel):
    """知识库问答响应。"""

    answer: str = Field(..., description="回答内容")
    fallback: bool = Field(default=False, description="是否降级模式（未调用模型/模型失败）")
    model: Optional[str] = Field(default=None, description="实际使用的模型")
    sources: list[dict] = Field(default_factory=list, description="引用来源片段")

