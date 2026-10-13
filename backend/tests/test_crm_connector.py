"""CRM/会员数据源连接器插件 pytest 用例。

覆盖：清单解析、backend 注入、监督建表、CSV 解析、REST 拉取（测试桩）、
数据归一与异常路径（缺字段/坏文件/网络失败）、SDK connector 门面全链路。
"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.plugin.registry import PluginRegistry
from app.core.plugin.runtime import PluginRuntime

REAL_PLUGIN_SRC = Path(__file__).resolve().parents[2] / "plugins" / "crm_connector"
PLUGIN_SRC = REAL_PLUGIN_SRC / "backend" / "src"
sys.path.insert(0, str(PLUGIN_SRC))

from connectors.base import ConnectorError  # noqa: E402
from connectors.csv_source import CsvConnector  # noqa: E402
from connectors.rest_source import RestConnector  # noqa: E402


@pytest.fixture()
def plugins_dir(tmp_path: Path) -> Path:
    """把真实 crm_connector 插件复制到临时目录，测试不污染项目仓库。"""
    dest = tmp_path / "plugins"
    shutil.copytree(REAL_PLUGIN_SRC, dest / "crm_connector")
    return dest


@pytest.fixture()
def session_factory() -> object:
    """sqlite 内存库会话工厂：单连接复用，供插件表与门面调用共用。"""
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def factory():
        return maker()

    return factory


@pytest.fixture()
def activated_ctx(plugins_dir: Path, session_factory):
    """全链路上下文：注册→加载 backend→监督建表→激活。"""
    registry = PluginRegistry(plugins_dir)
    runtime = PluginRuntime(registry, session_factory=session_factory)
    runtime.load_all()
    runtime.load_backend("crm_connector")
    runtime.provision_tables("crm_connector")
    ctx = runtime.activate("crm_connector")
    yield ctx
    runtime.deactivate("crm_connector")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---- 1. 清单与装载链路 ----

def test_manifest_entry_declared_and_parsed(plugins_dir: Path) -> None:
    """清单 entry 声明合法，registry 解析后 meta.entry 就绪。"""
    registry = PluginRegistry(plugins_dir)
    assert registry.discover() == ["crm_connector"]
    meta = registry.register("crm_connector")
    assert meta.entry == "backend.src.main:register"
    assert meta.namespace["tables"].startswith("os_crm_")


def test_load_backend_injects_connector_engine(plugins_dir: Path, session_factory) -> None:
    """内核按 entry 加载插件 backend，register 注入连接器引擎成功。"""
    runtime = PluginRuntime(PluginRegistry(plugins_dir), session_factory=session_factory)
    runtime.load_all()
    assert runtime._connector_engine is None
    mod = runtime.load_backend("crm_connector")
    assert mod is not None
    assert runtime._connector_engine is not None  # 已由 register 注入
    assert runtime.load_backend("crm_connector") is mod  # 幂等


def test_provision_tables_creates_crm_tables(plugins_dir: Path, session_factory) -> None:
    """内核监督建表：os_crm_* 三张表全部落库。"""
    runtime = PluginRuntime(PluginRegistry(plugins_dir), session_factory=session_factory)
    runtime.load_all()
    runtime.load_backend("crm_connector")
    tables = runtime.provision_tables("crm_connector")
    assert len(tables) == 3
    assert set(tables) == {"os_crm_source", "os_crm_sync_task", "os_crm_dataset"}


# ---- 2. CSV 接入 ----

def test_csv_ingest_normalizes_records(activated_ctx, tmp_path: Path) -> None:
    """CSV 导入成功：记录归一（member_id 转 str、points 转 int、balance 转 float）。"""
    csv_path = tmp_path / "members.csv"
    _write_csv(
        csv_path,
        ["member_id", "name", "phone", "level", "points", "balance"],
        [
            {"member_id": "1001", "name": "张三", "phone": "13800000001", "level": "gold", "points": "120", "balance": "88.5"},
            {"member_id": "1002", "name": "李四", "phone": "13800000002", "level": "silver", "points": "30", "balance": "0"},
        ],
    )

    src = activated_ctx.connector.create_source(
        source_type="csv", name="会员主档 CSV", config={"file_path": str(csv_path)}
    )
    result = activated_ctx.connector.ingest_csv(source_id=src["id"], file_path=str(csv_path))
    assert result["ok"] is True
    assert result["record_count"] == 2

    datasets = activated_ctx.connector.list_datasets(source_id=src["id"])
    assert len(datasets) == 1
    ds = activated_ctx.connector.get_dataset(dataset_id=datasets[0]["id"])
    assert ds["record_count"] == 2
    assert ds["dataset_type"] == "crm_member"
    assert ds["schema_version"] == "1.0"


def test_csv_missing_required_field(activated_ctx, tmp_path: Path) -> None:
    """异常路径：CSV 记录缺必填字段 member_id → 同步失败并记录 error。"""
    csv_path = tmp_path / "bad_members.csv"
    _write_csv(
        csv_path,
        ["member_id", "name"],
        [{"member_id": "1001", "name": "张三"}, {"member_id": "", "name": "缺ID"}],
    )

    src = activated_ctx.connector.create_source(
        source_type="csv", name="缺字段 CSV", config={"file_path": str(csv_path)}
    )
    result = activated_ctx.connector.ingest_csv(source_id=src["id"], file_path=str(csv_path))
    assert result["ok"] is False
    assert "缺少必填字段" in result["error"]


def test_csv_file_not_found(activated_ctx) -> None:
    """异常路径：CSV 文件不存在 → 同步失败并记录 error。"""
    src = activated_ctx.connector.create_source(
        source_type="csv", name="坏文件 CSV", config={"file_path": "Z:/no/such/file.csv"}
    )
    result = activated_ctx.connector.ingest_csv(source_id=src["id"], file_path="Z:/no/such/file.csv")
    assert result["ok"] is False
    assert "不存在" in result["error"]


def test_csv_connector_direct_rejects_bad_file(tmp_path: Path) -> None:
    """连接器层：坏文件（无表头）直接抛 ConnectorError。"""
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")
    connector = CsvConnector(1, "bad", {"file_path": str(empty_path)})
    with pytest.raises(ConnectorError, match="无表头|为空"):
        connector.ingest()


# ---- 3. REST 接入（测试桩传输层） ----

def test_rest_ingest_with_transport_stub() -> None:
    """REST 拉取成功：测试桩返回 JSON，记录归一化正确。"""
    payload = {
        "data": [
            {"id": "2001", "name": "王五", "email": "w@example.com", "points": "999", "balance": "12.3"},
        ]
    }

    def transport_stub(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://api.example.com/members"
        return 200, payload

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/members", "records_key": "data"},
        transport=transport_stub,
    )
    dataset = connector.ingest()
    assert dataset.record_count == 1
    rec = dataset.records[0]
    assert rec["member_id"] == "2001"
    assert rec["points"] == 999
    assert rec["balance"] == 12.3


def test_rest_http_error_propagates() -> None:
    """异常路径：REST 返回 HTTP 5xx → ConnectorError。"""

    def transport_stub(method, url, **kwargs):
        return 503, {"error": "service unavailable"}

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/members"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="HTTP 503"):
        connector.ingest()


def test_rest_network_failure_propagates() -> None:
    """异常路径：网络失败 → ConnectorError 传播。"""

    def transport_stub(method, url, **kwargs):
        raise ConnectorError("REST 拉取网络失败: 连接超时")

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/members"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="网络失败"):
        connector.ingest()


def test_rest_missing_records_key() -> None:
    """异常路径：响应缺少 records_key 指向的键 → ConnectorError。"""

    def transport_stub(method, url, **kwargs):
        return 200, {"items": [{"id": "1"}]}

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/members", "records_key": "data"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="缺少记录键"):
        connector.ingest()


def test_rest_missing_required_field() -> None:
    """异常路径：REST 记录缺必填字段 name → ConnectorError。"""

    def transport_stub(method, url, **kwargs):
        return 200, [{"id": "3001"}]

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/members"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="缺少必填字段"):
        connector.ingest()


# ---- 4. 数据源与门面 ----

def test_create_and_list_sources(activated_ctx) -> None:
    """数据源管理：创建 csv/rest 源后可列出，校验接入方式。"""
    src_csv = activated_ctx.connector.create_source(
        source_type="csv", name="CSV源", config={"file_path": "C:/tmp/a.csv"}
    )
    src_rest = activated_ctx.connector.create_source(
        source_type="rest", name="REST源", config={"url": "https://api.example.com"}
    )
    sources = activated_ctx.connector.list_sources()
    assert {s["id"] for s in sources} == {src_csv["id"], src_rest["id"]}

    with pytest.raises(Exception, match="不支持的接入方式"):
        activated_ctx.connector.create_source(
            source_type="ftp", name="坏源", config={}
        )


def test_sync_auto_mode_dispatches(activated_ctx, tmp_path: Path) -> None:
    """sync auto 模式按 source_type 自动分发到 csv。"""
    csv_path = tmp_path / "sync.csv"
    _write_csv(
        csv_path,
        ["member_id", "name"],
        [{"member_id": "1", "name": "自动同步"}],
    )
    src = activated_ctx.connector.create_source(
        source_type="csv", name="自动源", config={"file_path": str(csv_path)}
    )
    result = activated_ctx.connector.sync(source_id=src["id"], mode="auto")
    assert result["ok"] is True
    assert result["record_count"] == 1
