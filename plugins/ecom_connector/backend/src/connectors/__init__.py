"""数据源连接器实现子包（电商/交易）。

``base`` 提供可复用基类与归一化工具，``csv_source`` / ``rest_source``
为两种接入实现；复用 crm_connector 打样的 ConnectorBase/FieldMapping/
ConnectorDataset/ConnectorError 结构与 csv/rest 双接入模式。
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
