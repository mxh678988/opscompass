"""数据源连接器实现子包。

``base`` 提供可复用基类与归一化工具，``csv_source`` / ``rest_source``
为两种接入实现；后续电商/交易、广告投放连接器可复制本子包结构，
仅替换映射规则与拉取逻辑。
"""

from .base import ConnectorBase, ConnectorDataset, ConnectorError, FieldMapping  # noqa: F401
from .csv_source import CsvConnector  # noqa: F401
from .rest_source import RestConnector  # noqa: F401

__all__ = [
    "ConnectorBase",
    "ConnectorDataset",
    "ConnectorError",
    "CsvConnector",
    "FieldMapping",
    "RestConnector",
]
