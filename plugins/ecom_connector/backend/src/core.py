"""电商/交易数据源连接器引擎：动作分发 + 数据源/数据集/同步流水管理。

引擎通过 ``create_for_plugin`` 工厂注入内核（runtime.inject_connector_engine），
内核 SDK connector.* 门面以 action 分发到本引擎；插件侧不直连内核模块。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from .connectors import ConnectorBase, ConnectorError
from .connectors.csv_source import CsvConnector
from .connectors.rest_source import RestConnector
from .database import EcomDataset, EcomSource, EcomSyncTask

SUPPORTED_SOURCE_TYPES = ("csv", "rest")
DATASET_SCHEMA_VERSION = "1.0"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EcomConnectorEngine:
    """连接器引擎：每个动作均以独立会话（db）执行。"""

    def __init__(self, db: Any, plugin_id: str) -> None:
        self.db = db
        self.plugin_id = plugin_id

    # ---- 数据源管理 ----

    def create_source(self, source_type: str, name: str, config: dict[str, Any]) -> dict[str, Any]:
        """登记数据源；config 内可含文件路径/端点/映射等连接器参数。"""
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise ConnectorError(f"不支持的接入方式: {source_type!r}，支持 {SUPPORTED_SOURCE_TYPES}")
        if not name or not name.strip():
            raise ConnectorError("数据源名称不能为空")
        source = EcomSource(
            plugin_id=self.plugin_id,
            source_type=source_type,
            name=name.strip(),
            config=config or {},
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return self._source_summary(source)

    def list_sources(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(EcomSource)
            .where(EcomSource.plugin_id == self.plugin_id)
            .order_by(EcomSource.id.desc())
        ).scalars().all()
        return [self._source_summary(r) for r in rows]

    def _get_source(self, source_id: int) -> EcomSource:
        row = self.db.get(EcomSource, source_id)
        if row is None or row.plugin_id != self.plugin_id:
            raise ConnectorError(f"数据源不存在: {source_id}")
        return row

    @staticmethod
    def _source_summary(row: EcomSource) -> dict[str, Any]:
        return {
            "id": row.id,
            "source_type": row.source_type,
            "name": row.name,
            "config": row.config,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # ---- 连接器构建 ----

    def _build_connector(self, source: EcomSource) -> ConnectorBase:
        try:
            if source.source_type == "csv":
                return CsvConnector(source.id, source.name, source.config)
            if source.source_type == "rest":
                return RestConnector(source.id, source.name, source.config)
        except ConnectorError:
            raise
        except Exception as exc:  # 配置异常统一转业务错误
            raise ConnectorError(f"构建连接器失败: {exc}") from exc
        raise ConnectorError(f"不支持的接入方式: {source.source_type!r}")

    # ---- 接入执行 ----

    def ingest_csv(self, source_id: int, file_path: str) -> dict[str, Any]:
        """以指定 CSV 文件导入（允许覆盖数据源默认路径）。"""
        source = self._get_source(source_id)
        if source.source_type != "csv":
            raise ConnectorError(f"数据源 {source_id} 不是 CSV 类型")
        connector = CsvConnector(source.id, source.name, {**source.config, "file_path": file_path})
        return self._run_ingest(source, connector, mode="csv")

    def fetch_rest(self, source_id: int) -> dict[str, Any]:
        """按 REST 数据源配置拉取并归一。"""
        source = self._get_source(source_id)
        if source.source_type != "rest":
            raise ConnectorError(f"数据源 {source_id} 不是 REST 类型")
        connector = RestConnector(source.id, source.name, source.config)
        return self._run_ingest(source, connector, mode="rest")

    def sync(self, source_id: int, mode: str = "auto") -> dict[str, Any]:
        """通用同步入口：auto 按 source_type 自动选择 csv/rest。"""
        source = self._get_source(source_id)
        if mode == "auto":
            mode = source.source_type
        if mode == "csv":
            return self.ingest_csv(source_id, source.config.get("file_path", ""))
        if mode == "rest":
            return self.fetch_rest(source_id)
        raise ConnectorError(f"不支持的同步模式: {mode!r}")

    def _run_ingest(self, source: EcomSource, connector: ConnectorBase, *, mode: str) -> dict[str, Any]:
        """执行接入并落库：成功写数据集+success 流水，失败写 failed 流水。"""
        task = EcomSyncTask(
            plugin_id=self.plugin_id,
            source_id=source.id,
            mode=mode,
            status="failed",
            records_count=0,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(task)
        self.db.flush()
        try:
            dataset = connector.ingest()
        except ConnectorError as exc:
            task.status = "failed"
            task.error = str(exc)
            task.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            return {"ok": False, "source_id": source.id, "error": str(exc)}

        record = EcomDataset(
            plugin_id=self.plugin_id,
            source_id=source.id,
            dataset_type=dataset.dataset_type,
            schema_version=dataset.schema_version,
            record_count=len(dataset.records),
            records=dataset.records,
            normalized_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.flush()
        dataset_id = record.id
        task.status = "success"
        task.records_count = len(dataset.records)
        task.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        return {
            "ok": True,
            "source_id": source.id,
            "dataset_id": dataset_id,
            "record_count": len(dataset.records),
            "dataset_type": dataset.dataset_type,
            "schema_version": dataset.schema_version,
            "normalized_at": dataset.normalized_at,
        }

    # ---- 数据集查询 ----

    def list_datasets(self, source_id: Optional[int] = None) -> list[dict[str, Any]]:
        stmt = select(EcomDataset).where(EcomDataset.plugin_id == self.plugin_id)
        if source_id is not None:
            stmt = stmt.where(EcomDataset.source_id == source_id)
        rows = self.db.execute(stmt.order_by(EcomDataset.id.desc())).scalars().all()
        return [self._dataset_summary(r) for r in rows]

    def get_dataset(self, dataset_id: int) -> dict[str, Any]:
        row = self.db.get(EcomDataset, dataset_id)
        if row is None or row.plugin_id != self.plugin_id:
            raise ConnectorError(f"数据集不存在: {dataset_id}")
        return self._dataset_summary(row)

    @staticmethod
    def _dataset_summary(row: EcomDataset) -> dict[str, Any]:
        return {
            "id": row.id,
            "source_id": row.source_id,
            "dataset_type": row.dataset_type,
            "schema_version": row.schema_version,
            "record_count": row.record_count,
            "normalized_at": row.normalized_at.isoformat() if row.normalized_at else None,
        }


def create_for_plugin(
    db: Any,
    plugin_id: str,
    action: str,
    params: dict[str, Any],
    **kwargs: Any,
) -> Any:
    """插件引擎工厂：按 action 分发到引擎方法。

    与内核 runtime._make_connector 约定一致；未知动作抛 ConnectorError。
    """
    engine = EcomConnectorEngine(db, plugin_id)
    handler = getattr(engine, action, None)
    if handler is None or not callable(handler):
        raise ConnectorError(f"连接器未知动作: {action!r}")
    return handler(**params)
