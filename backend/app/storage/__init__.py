"""存储适配层：按接入数据类型路由到合适存储实现。

模块划分：
- base       公共契约（能力描述 / 基类）
- relational 关系型数据（PostgreSQL 表）
- timeseries 时序指标（PostgreSQL 分区表 + 时间索引）
- search     全文检索（PostgreSQL tsvector + GIN，pg_trgm 可选）
- cache      热点缓存（Redis，可降级）
- files      文件对象（本地受管目录 + 校验哈希）
- routing    数据源类型识别与引擎路由
- registry   适配器注册表与统一编排
- consistency 跨存储数据一致性对账

注意：本包不在模块级导入 app.services.*，避免与业务服务形成循环依赖。
"""

from app.storage.base import AdapterCapability, StorageAdapter  # noqa: F401
from app.storage.cache import cache_adapter  # noqa: F401
from app.storage.files import file_adapter  # noqa: F401
from app.storage.relational import relational_adapter  # noqa: F401
from app.storage.search import search_adapter  # noqa: F401
from app.storage.timeseries import timeseries_adapter  # noqa: F401

__all__ = [
    "AdapterCapability",
    "StorageAdapter",
    "cache_adapter",
    "file_adapter",
    "relational_adapter",
    "search_adapter",
    "timeseries_adapter",
]
