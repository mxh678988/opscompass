"""广告投放数据源连接器插件 pytest 用例。

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

REAL_PLUGIN_SRC = Path(__file__).resolve().parents[2] / "plugins" / "ads_connector"
PLUGIN_SRC = REAL_PLUGIN_SRC / "backend" / "src"
sys.path.insert(0, str(PLUGIN_SRC))

# 多插件测试在同一 pytest 进程运行时，包名 connectors 可能命中其它插件已
# 缓存的实现；每次导入前弹出缓存，强制加载本插件自己的 connectors 包。
for _name in list(sys.modules):
    if _name == "connectors" or _name.startswith("connectors."):
        sys.modules.pop(_name, None)

from connectors.base import ConnectorError  # noqa: E402
from connectors.csv_source import CsvConnector  # noqa: E402
from connectors.rest_source import RestConnector  # noqa: E402


@pytest.fixture()
def plugins_dir(tmp_path: Path) -> Path:
    """把真实 ads_connector 插件复制到临时目录，测试不污染项目仓库。"""
    dest = tmp_path / "plugins"
    shutil.copytree(REAL_PLUGIN_SRC, dest / "ads_connector")
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
    runtime.load_backend("ads_connector")
    runtime.provision_tables("ads_connector")
    ctx = runtime.activate("ads_connector")
    yield ctx
    runtime.deactivate("ads_connector")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---- 1. 清单与装载链路 ----

def test_manifest_entry_declared_and_parsed(plugins_dir: Path) -> None:
    """清单 entry 声明合法，registry 解析后 meta.entry 就绪。"""
    registry = PluginRegistry(plugins_dir)
    assert registry.discover() == ["ads_connector"]
    meta = registry.register("ads_connector")
    assert meta.entry == "backend.src.main:register"
    assert meta.namespace["tables"].startswith("os_ads_")


def test_load_backend_injects_connector_engine(plugins_dir: Path, session_factory) -> None:
    """内核按 entry 加载插件 backend，register 注入连接器引擎成功。"""
    runtime = PluginRuntime(PluginRegistry(plugins_dir), session_factory=session_factory)
    runtime.load_all()
    assert runtime._connector_engine is None
    mod = runtime.load_backend("ads_connector")
    assert mod is not None
    assert runtime._connector_engine is not None  # 已由 register 注入
    assert runtime.load_backend("ads_connector") is mod  # 幂等


def test_provision_tables_creates_ads_tables(plugins_dir: Path, session_factory) -> None:
    """内核监督建表：os_ads_* 三张表全部落库。"""
    runtime = PluginRuntime(PluginRegistry(plugins_dir), session_factory=session_factory)
    runtime.load_all()
    runtime.load_backend("ads_connector")
    tables = runtime.provision_tables("ads_connector")
    assert len(tables) == 3
    assert set(tables) == {"os_ads_source", "os_ads_sync_task", "os_ads_dataset"}


# ---- 2. CSV 接入 ----

def test_csv_ingest_normalizes_records(activated_ctx, tmp_path: Path) -> None:
    """CSV 导入成功：记录归一（spend 转 float、impressions/clicks/conversions 转 int）。"""
    csv_path = tmp_path / "ads_daily.csv"
    _write_csv(
        csv_path,
        ["campaign", "ad_group", "spend", "impressions", "clicks", "conversions", "date"],
        [
            {"campaign": "夏季大促", "ad_group": "SKU-001-搜索", "spend": "1200.50", "impressions": "50000", "clicks": "800", "conversions": "45", "date": "2026-10-01"},
            {"campaign": "夏季大促", "ad_group": "SKU-002-信息流", "spend": "860.00", "impressions": "30000", "clicks": "420", "conversions": "18", "date": "2026-10-01"},
        ],
    )

    src = activated_ctx.connector.create_source(
        source_type="csv", name="投放日报 CSV", config={"file_path": str(csv_path)}
    )
    result = activated_ctx.connector.ingest_csv(source_id=src["id"], file_path=str(csv_path))
    assert result["ok"] is True
    assert result["record_count"] == 2

    datasets = activated_ctx.connector.list_datasets(source_id=src["id"])
    assert len(datasets) == 1
    ds = activated_ctx.connector.get_dataset(dataset_id=datasets[0]["id"])
    assert ds["record_count"] == 2
    assert ds["dataset_type"] == "ads_campaign_daily"
    assert ds["schema_version"] == "1.0"


def test_csv_missing_required_field(activated_ctx, tmp_path: Path) -> None:
    """异常路径：CSV 记录缺必填字段 ad_group → 同步失败并记录 error。"""
    csv_path = tmp_path / "bad_ads.csv"
    _write_csv(
        csv_path,
        ["campaign", "ad_group"],
        [{"campaign": "夏季大促", "ad_group": "组A"}, {"campaign": "秋季上新", "ad_group": ""}],
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
        source_type="csv", name="坏文件 CSV", config={"file_path": "Z:/no/such/ads.csv"}
    )
    result = activated_ctx.connector.ingest_csv(source_id=src["id"], file_path="Z:/no/such/ads.csv")
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
            {"campaign_id": "C-100", "ad_group_id": "G-200", "spend": "500.25", "impressions": "100000", "clicks": "1200", "conversions": "66", "date": "2026-10-03"},
        ]
    }

    def transport_stub(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://api.example.com/ads/report"
        return 200, payload

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/ads/report", "records_key": "data"},
        transport=transport_stub,
    )
    dataset = connector.ingest()
    assert dataset.record_count == 1
    rec = dataset.records[0]
    assert rec["campaign"] == "C-100"
    assert rec["ad_group"] == "G-200"
    assert rec["spend"] == 500.25
    assert rec["impressions"] == 100000
    assert rec["clicks"] == 1200
    assert rec["conversions"] == 66


def test_rest_http_error_propagates() -> None:
    """异常路径：REST 返回 HTTP 5xx → ConnectorError。"""

    def transport_stub(method, url, **kwargs):
        return 500, {"error": "internal error"}

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/ads/report"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="HTTP 500"):
        connector.ingest()


def test_rest_network_failure_propagates() -> None:
    """异常路径：网络失败 → ConnectorError 传播。"""

    def transport_stub(method, url, **kwargs):
        raise ConnectorError("REST 拉取网络失败: 连接超时")

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/ads/report"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="网络失败"):
        connector.ingest()


def test_rest_missing_records_key() -> None:
    """异常路径：响应缺少 records_key 指向的键 → ConnectorError。"""

    def transport_stub(method, url, **kwargs):
        return 200, {"items": [{"campaign_id": "1"}]}

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/ads/report", "records_key": "data"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="缺少记录键"):
        connector.ingest()


def test_rest_missing_required_field() -> None:
    """异常路径：REST 记录缺必填字段 ad_group_id → ConnectorError。"""

    def transport_stub(method, url, **kwargs):
        return 200, [{"campaign_id": "C-300"}]

    connector = RestConnector(
        1, "REST源", {"url": "https://api.example.com/ads/report"},
        transport=transport_stub,
    )
    with pytest.raises(ConnectorError, match="缺少必填字段"):
        connector.ingest()


# ---- 4. 数据源与门面 ----

def test_create_and_list_sources(activated_ctx) -> None:
    """数据源管理：创建 csv/rest 源后可列出，校验接入方式。"""
    src_csv = activated_ctx.connector.create_source(
        source_type="csv", name="CSV源", config={"file_path": "C:/tmp/ads.csv"}
    )
    src_rest = activated_ctx.connector.create_source(
        source_type="rest", name="REST源", config={"url": "https://api.example.com/ads/report"}
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
        ["campaign", "ad_group"],
        [{"campaign": "C1", "ad_group": "G1"}],
    )
    src = activated_ctx.connector.create_source(
        source_type="csv", name="自动源", config={"file_path": str(csv_path)}
    )
    result = activated_ctx.connector.sync(source_id=src["id"], mode="auto")
    assert result["ok"] is True
    assert result["record_count"] == 1
