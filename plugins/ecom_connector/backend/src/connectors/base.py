"""可复用的数据源连接器基类与归一化工具。

电商/交易、广告投放连接器只需继承 ``ConnectorBase``、实现
``ingest()`` 并声明自己的 ``FieldMapping`` 列表即可复用归一化、
校验与数据集产出链路（与 crm_connector 打样共享同一套结构）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


class ConnectorError(Exception):
    """连接器业务异常：携带用户可读的失败原因。

    涵盖缺字段、坏文件、网络失败等异常路径；引擎捕获后写入
    同步任务流水（status=failed, error=...）。
    """


@dataclass(frozen=True)
class FieldMapping:
    """字段映射规则：把原始记录字段归一为目标字段。

    ``source_field``：原始字段名；``target_field``：归一后字段名
    （缺省与 source_field 相同）；``required``：缺失即报错；
    ``transform``：类型转换（str/int/float）。
    """

    source_field: str
    target_field: Optional[str] = None
    required: bool = False
    transform: Optional[str] = None

    def resolve_target(self) -> str:
        return self.target_field or self.source_field

    def coerce(self, value: Any) -> Any:
        if value is None:
            return None
        if self.transform == "int":
            try:
                return int(float(value))
            except (TypeError, ValueError) as exc:
                raise ConnectorError(
                    f"字段 {self.source_field} 无法转换为整数: {value!r}"
                ) from exc
        if self.transform == "float":
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise ConnectorError(
                    f"字段 {self.source_field} 无法转换为浮点数: {value!r}"
                ) from exc
        return str(value) if not isinstance(value, str) else value


@dataclass
class ConnectorDataset:
    """统一归一化后的平台数据集（平台可消费结构）。

    ``records`` 为 dict 列表，每项为归一后的记录（键为 target 字段）；
    ``schema_version`` 标识归一协议版本，供下游消费端做兼容判断。
    """

    dataset_type: str
    schema_version: str
    records: list[dict[str, Any]] = field(default_factory=list)
    normalized_at: str = ""

    def __post_init__(self) -> None:
        if not self.normalized_at:
            self.normalized_at = datetime.now(timezone.utc).isoformat()

    @property
    def record_count(self) -> int:
        return len(self.records)

    def summary(self) -> dict[str, Any]:
        return {
            "dataset_type": self.dataset_type,
            "schema_version": self.schema_version,
            "record_count": self.record_count,
            "normalized_at": self.normalized_at,
        }


def parse_mappings(mappings: Optional[list[dict[str, Any]]]) -> list[FieldMapping]:
    """从数据源配置解析字段映射；None 表示使用连接器默认映射。"""
    if not mappings:
        return []
    result: list[FieldMapping] = []
    for item in mappings:
        result.append(
            FieldMapping(
                source_field=str(item["source_field"]),
                target_field=item.get("target_field"),
                required=bool(item.get("required", False)),
                transform=item.get("transform"),
            )
        )
    return result


class ConnectorBase:
    """连接器基类：声明接入方式并统一产出 ConnectorDataset。

    子类需实现：``source_type`` 与 ``ingest()``；可覆盖
    ``normalize_record()`` 做记录级后处理（如派生字段）。
    """

    source_type: str = "base"
    default_mappings: list[FieldMapping] = []

    def __init__(
        self,
        source_id: int,
        name: str,
        config: dict[str, Any],
        *,
        mappings: Optional[list[FieldMapping]] = None,
    ) -> None:
        self.source_id = source_id
        self.name = name
        self.config = config or {}
        self.mappings = mappings if mappings is not None else list(self.default_mappings)

    # ---- 归一化 ----

    def normalize_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        """按字段映射归一单条记录；缺必填字段抛 ConnectorError。"""
        out: dict[str, Any] = {}
        missing: list[str] = []
        for mapping in self.mappings:
            value = raw.get(mapping.source_field, _MISSING)
            if value is _MISSING or (isinstance(value, str) and not value.strip()):
                if mapping.required:
                    missing.append(mapping.source_field)
                continue
            out[mapping.resolve_target()] = mapping.coerce(value)
        if missing:
            raise ConnectorError(
                f"记录缺少必填字段: {', '.join(sorted(missing))}"
            )
        return out

    def normalize_records(
        self,
        raw_records: list[dict[str, Any]],
        *,
        dataset_type: str,
        schema_version: str,
    ) -> ConnectorDataset:
        """批量归一原始记录为平台数据集。"""
        records = [self.normalize_record(r) for r in raw_records]
        return ConnectorDataset(
            dataset_type=dataset_type,
            schema_version=schema_version,
            records=records,
        )

    # ---- 子类实现 ----

    def ingest(self) -> ConnectorDataset:
        """拉取/读取原始数据并归一，返回平台数据集。子类必须实现。"""
        raise NotImplementedError(f"{type(self).__name__}.ingest() 未实现")


_MISSING = object()


def default_transport(
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    """默认 HTTP 传输层：返回 (status_code, 解析后的 JSON)。

    基于 urllib.request，避免引入外部依赖；测试中可注入替身传输层
    模拟成功/失败。
    """
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    target = url
    if params:
        target = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(target, method=method.upper(), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise ConnectorError(f"REST 拉取 HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ConnectorError(f"REST 拉取网络失败: {exc.reason}") from exc
    except OSError as exc:
        raise ConnectorError(f"REST 拉取网络失败: {exc}") from exc
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectorError(f"REST 响应不是合法 JSON: {exc}") from exc
    return status, data


TransportFn = Callable[..., tuple[int, Any]]
