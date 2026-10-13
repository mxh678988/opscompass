"""CSV 文件接入连接器：读取本地 CSV 并归一为平台数据集。"""

from __future__ import annotations

import csv
import os
from typing import Any, Optional

from .base import ConnectorBase, ConnectorDataset, ConnectorError, FieldMapping


class CsvConnector(ConnectorBase):
    """CRM/会员 CSV 数据源。

    config 支持：
    - file_path: CSV 文件绝对路径（必填）
    - delimiter: 分隔符，默认 ","
    - mappings: 字段映射列表，缺省使用 DEFAULT_MAPPINGS
    - dataset_type: 数据集类型，默认 crm_member
    """

    source_type = "csv"

    default_mappings: list[FieldMapping] = [
        FieldMapping("member_id", "member_id", required=True, transform="str"),
        FieldMapping("name", "name", required=True),
        FieldMapping("phone", "phone"),
        FieldMapping("email", "email"),
        FieldMapping("level", "level"),
        FieldMapping("points", "points", transform="int"),
        FieldMapping("balance", "balance", transform="float"),
    ]

    def __init__(self, source_id: int, name: str, config: dict[str, Any], **kwargs: Any) -> None:
        mappings = kwargs.pop("mappings", None)
        super().__init__(source_id, name, config, mappings=mappings)
        self.file_path = config.get("file_path") or config.get("path")
        if not self.file_path:
            raise ConnectorError("CSV 数据源缺少 file_path 配置")
        self.delimiter = config.get("delimiter", ",")
        self.dataset_type = config.get("dataset_type", "crm_member")
        self.schema_version = config.get("schema_version", "1.0")

    def ingest(self) -> ConnectorDataset:
        """读取 CSV 文件并归一；文件不存在/空/坏行均按异常路径处理。"""
        path = os.fspath(self.file_path)
        if not os.path.exists(path):
            raise ConnectorError(f"CSV 文件不存在: {path}")
        if not os.path.isfile(path):
            raise ConnectorError(f"CSV 路径不是文件: {path}")

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh, delimiter=self.delimiter)
                if reader.fieldnames is None:
                    raise ConnectorError(f"CSV 文件无表头或为空: {path}")
                raw_records = [row for row in reader]
        except (OSError, UnicodeDecodeError) as exc:
            raise ConnectorError(f"CSV 文件读取失败: {exc}") from exc

        if not raw_records:
            raise ConnectorError(f"CSV 文件为空: {path}")

        return self.normalize_records(
            raw_records,
            dataset_type=self.dataset_type,
            schema_version=self.schema_version,
        )
