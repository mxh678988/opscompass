"""CRM/会员数据源连接器插件自有数据表结构。

由内核 provision_tables 在内核监督下建表（M2 设计约束，插件不得自行
建表）；表名遵循清单 namespace.tables 前缀 os_crm_。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrmSource(Base):
    """已登记的数据源（CSV 文件源 / REST API 源）。"""

    __tablename__ = "os_crm_source"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin_id = Column(String(64), nullable=False, index=True)
    source_type = Column(String(16), nullable=False, index=True)  # csv | rest
    name = Column(String(128), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class CrmSyncTask(Base):
    """同步任务流水：记录每次 csv/rest 接入的成败与记录数。"""

    __tablename__ = "os_crm_sync_task"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin_id = Column(String(64), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    mode = Column(String(16), nullable=False)  # csv | rest
    status = Column(String(16), nullable=False, index=True)  # success | failed
    records_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=_utcnow)
    finished_at = Column(DateTime, nullable=True)


class CrmDataset(Base):
    """归一化后的平台数据集（统一可消费结构）。"""

    __tablename__ = "os_crm_dataset"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin_id = Column(String(64), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    dataset_type = Column(String(32), nullable=False, default="crm_member")
    schema_version = Column(String(16), nullable=False, default="1.0")
    record_count = Column(Integer, nullable=False, default=0)
    records = Column(JSON, nullable=False, default=list)
    normalized_at = Column(DateTime, nullable=False, default=_utcnow)
