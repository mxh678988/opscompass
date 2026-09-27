"""临时统计脚本：输出 P2 存储适配层落地现状（验证结束后可移除）。"""

import psycopg

from app.core.config import settings

QUERIES = [
    ("alembic_version", "select version_num from alembic_version"),
    (
        "ts_partition_count",
        "select count(1) from pg_tables where tablename like 'oc_ts_metric_point%'",
    ),
    ("doc_index_rows", "select count(1) from oc_doc_index"),
    ("route_rules", "select count(1) from oc_storage_route_rule"),
    ("consistency_rows", "select count(1) from oc_storage_consistency_check"),
    ("doc_index_indexes", "select indexname from pg_indexes where tablename='oc_doc_index'"),
    (
        "ts_table_indexes",
        "select indexname from pg_indexes where tablename='oc_ts_metric_point'",
    ),
    (
        "ts_tables",
        "select tablename from pg_tables where tablename like 'oc_ts_metric_point%' order by 1",
    ),
]

conn = psycopg.connect(settings.DATABASE_URL.replace("postgresql+psycopg", "postgresql"))
cur = conn.cursor()
for label, sql in QUERIES:
    try:
        cur.execute(sql)
        print(label, "=", [r[0] for r in cur.fetchall()])
    except Exception as exc:  # pragma: no cover
        conn.rollback()
        print(label, "ERR", type(exc).__name__, exc)
