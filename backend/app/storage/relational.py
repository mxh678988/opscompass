"""关系型数据适配器：PostgreSQL 表（结构化实体的默认落点）。

职责：
1. 提供关系型存储的能力探测与规模统计（表数量、行数、占用空间、连接状态）；
2. 为路由层提供「关系型数据类型」的统一入口，便于将来替换为其他 RDBMS。
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.storage.base import AdapterCapability

logger = logging.getLogger(__name__)

# 适配层关注的核心业务表（用于规模统计与对账范围展示）
CORE_TABLES = (
    "oc_tenant",
    "oc_data_source",
    "oc_metric",
    "oc_metric_value",
    "oc_metric_dimension",
    "oc_import_task",
    "oc_storage_route_rule",
    "oc_doc_index",
    "oc_ts_metric_point",
    "oc_storage_consistency_check",
)


class RelationalAdapter:
    """关系型存储适配器（PostgreSQL）。"""

    kind = "relational"
    engine = "postgresql"
    label = "关系型表存储"

    def capability(self, db=None) -> AdapterCapability:
        detail: dict = {"tables": 0, "server_version": ""}
        available = False
        try:
            if db is not None:
                row = db.execute(
                    text(
                        "SELECT current_database() AS db, current_user AS usr, "
                        "version() AS ver, "
                        "(SELECT count(*) FROM information_schema.tables "
                        " WHERE table_schema = 'public') AS tables"
                    )
                ).one()
                detail = {
                    "database": row.db,
                    "user": row.usr,
                    "server_version": str(row.ver).split(",")[0],
                    "tables": int(row.tables),
                    "core_tables": len(CORE_TABLES),
                }
                available = True
        except Exception as exc:
            detail = {"error": f"{type(exc).__name__}: {exc}"[:255]}
        return AdapterCapability(
            kind=self.kind,
            engine=self.engine,
            label=self.label,
            available=available,
            detail=detail,
        )

    def stats(self, db=None) -> dict:
        table_counts: dict[str, int] = {}
        size_pretty = ""
        if db is not None:
            try:
                for name in CORE_TABLES:
                    exists = db.execute(
                        text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name}
                    ).scalar()
                    if exists:
                        table_counts[name] = int(
                            db.execute(text(f"SELECT count(*) FROM {name}")).scalar() or 0
                        )
                size_pretty = str(
                    db.execute(
                        text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                    ).scalar()
                    or ""
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("relational stats failed: %s", exc)
        return {
            "kind": self.kind,
            "engine": self.engine,
            "database_size": size_pretty,
            "table_counts": table_counts,
        }


relational_adapter = RelationalAdapter()
