"""REST API 接入连接器（电商/交易）：拉取远端 JSON 并归一为平台数据集。

传输层默认走 ``default_transport``（urllib）；测试通过注入替身
``transport`` 模拟成功/网络失败，无需真实网络。
"""

from __future__ import annotations

from typing import Any, Optional

from .base import (
    ConnectorBase,
    ConnectorDataset,
    ConnectorError,
    FieldMapping,
    TransportFn,
    default_transport,
)


class RestConnector(ConnectorBase):
    """电商/交易 REST 数据源。

    config 支持：
    - url: 端点地址（必填）
    - method: GET/POST，默认 GET
    - headers: 请求头（如 Authorization）
    - params: 查询参数
    - records_key: 记录数组所在键，如 "data"；缺省取整个 JSON 列表
    - timeout: 超时秒数，默认 15
    - mappings: 字段映射列表，缺省使用 DEFAULT_MAPPINGS
    - dataset_type: 数据集类型，默认 ecom_order
    """

    source_type = "rest"

    default_mappings: list[FieldMapping] = [
        FieldMapping("id", "order_id", required=True, transform="str"),
        FieldMapping("sku", "sku", required=True),
        FieldMapping("amount", "amount", transform="float"),
        FieldMapping("quantity", "quantity", transform="int"),
        FieldMapping("order_time", "order_time"),
        FieldMapping("channel", "channel"),
    ]

    def __init__(
        self,
        source_id: int,
        name: str,
        config: dict[str, Any],
        *,
        transport: Optional[TransportFn] = None,
        **kwargs: Any,
    ) -> None:
        mappings = kwargs.pop("mappings", None)
        super().__init__(source_id, name, config, mappings=mappings)
        self.url = config.get("url")
        if not self.url:
            raise ConnectorError("REST 数据源缺少 url 配置")
        self.method = config.get("method", "GET")
        self.headers = config.get("headers") or {}
        self.params = config.get("params") or {}
        self.records_key = config.get("records_key")
        self.timeout = float(config.get("timeout", 15.0))
        self.dataset_type = config.get("dataset_type", "ecom_order")
        self.schema_version = config.get("schema_version", "1.0")
        self._transport = transport or default_transport

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        """从响应 JSON 中提取记录数组。"""
        data: Any = payload
        if self.records_key:
            for key in self.records_key.split("."):
                if not isinstance(data, dict) or key not in data:
                    raise ConnectorError(
                        f"REST 响应缺少记录键: {self.records_key!r}"
                    )
                data = data[key]
        if not isinstance(data, list):
            raise ConnectorError("REST 响应记录必须为数组")
        if not all(isinstance(item, dict) for item in data):
            raise ConnectorError("REST 响应记录必须为对象")
        return data

    def ingest(self) -> ConnectorDataset:
        """拉取远端数据并归一；网络失败/缺键/坏负载均按异常路径处理。"""
        status, payload = self._transport(
            self.method,
            self.url,
            headers=self.headers,
            params=self.params,
            timeout=self.timeout,
        )
        if status >= 400:
            raise ConnectorError(f"REST 拉取失败: HTTP {status}")
        raw_records = self._extract_records(payload)
        if not raw_records:
            raise ConnectorError("REST 响应记录为空")
        return self.normalize_records(
            raw_records,
            dataset_type=self.dataset_type,
            schema_version=self.schema_version,
        )
