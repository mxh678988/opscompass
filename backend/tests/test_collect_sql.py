"""采集服务（数据库直连）单元测试。

固化 0.10.1 真实数据源验证中踩到的坑，避免后续改动回退：

- Hive 空口令不得拼成 ``user:@``：PyHive 仅在 LDAP/CUSTOM 模式下接受 password，
  拼出空串口令会触发 ``ValueError: Password should be set if and only if ...``；
- Hive 不接受 ``connect_timeout`` 连接参数（误传抛 TypeError），配置口令时按 LDAP 认证；
- ClickHouse 依赖 ``clickhouse-connect``，需同时给出 connect_timeout 与 send_receive_timeout；
- 驱动缺失、类型未接入、表名非法等一律按 ``CollectError`` 返回，不得抛 500。

本模块只做纯函数级断言：不连数据库、不访问网络、不落库。
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.datasource import DataSource
from app.services import collect_service
from app.services.collect_service import (
    API_MAX_RECORDS,
    SQL_SUPPORTED_TYPES,
    SQL_TABLE_PATTERN,
    SQL_TIMEOUT_SECONDS,
    CollectError,
    _build_sql_url,
    _connect_args,
    _extract_records,
    _is_public_host,
    compute_next_run,
)


def _source(ds_type: str, password_enc=None, username="tester", **kwargs) -> DataSource:
    """构造不入库的 DataSource 实例，仅用于纯函数入参。"""
    fields = {
        "tenant_id": 1,
        "code": f"src_{ds_type}",
        "name": f"测试源 {ds_type}",
        "ds_type": ds_type,
        "host": "db.example.com",
        "port": 10000 if ds_type == "hive" else 5432,
        "db_name": "demo",
        "username": username,
        "password_enc": password_enc,
    }
    fields.update(kwargs)
    return DataSource(**fields)


# ---------------------------------------------------------------- 驱动注册表


def test_supported_types_cover_four_sql_engines() -> None:
    assert set(SQL_SUPPORTED_TYPES) == {"postgresql", "mysql", "clickhouse", "hive"}


@pytest.mark.parametrize(
    ("ds_type", "driver"),
    [
        ("postgresql", "postgresql+psycopg"),
        ("mysql", "mysql+pymysql"),
        ("clickhouse", "clickhousedb+connect"),
        ("hive", "hive"),
    ],
)
def test_driver_url_scheme(ds_type: str, driver: str) -> None:
    assert SQL_SUPPORTED_TYPES[ds_type][0] == driver


def test_hive_driver_module_is_tuple_with_sasl() -> None:
    """Hive 需同时校验 pyhive 与 thrift_sasl（thrift 为传递依赖）。"""
    modules = SQL_SUPPORTED_TYPES["hive"][1]
    assert isinstance(modules, tuple)
    assert "pyhive" in modules and "thrift_sasl" in modules


def test_clickhouse_driver_module_is_single_string() -> None:
    assert SQL_SUPPORTED_TYPES["clickhouse"][1] == "clickhouse_connect"


# ---------------------------------------------------------------- 连接串拼装


def test_unsupported_type_raises_collect_error() -> None:
    with pytest.raises(CollectError, match="尚未接入"):
        _build_sql_url(_source("oracle"))


def test_missing_host_raises_collect_error() -> None:
    with pytest.raises(CollectError, match="未配置主机/端口"):
        _build_sql_url(_source("postgresql", host=None))


def test_missing_db_name_raises_collect_error() -> None:
    with pytest.raises(CollectError, match="未配置库名"):
        _build_sql_url(_source("postgresql", db_name=None))


def test_missing_driver_module_raises_collect_error(monkeypatch) -> None:
    """驱动缺失时应返回 CollectError（提示安装），而不是 ImportError 冒泡。"""
    monkeypatch.setitem(
        collect_service.SQL_SUPPORTED_TYPES,
        "fakeengine",
        ("fakeengine://", "definitely_not_installed_module_xyz"),
    )
    with pytest.raises(CollectError, match="未安装"):
        _build_sql_url(_source("fakeengine"))


def test_hive_without_password_omits_empty_password_segment() -> None:
    """空口令 Hive 源：URL 中不得出现 ``user:@``（本轮踩坑点）。"""
    url = _build_sql_url(_source("hive", username="hive"))
    assert url == "hive://hive@db.example.com:10000/demo"
    assert ":@" not in url


def test_hive_without_password_and_user_has_clean_netloc() -> None:
    url = _build_sql_url(_source("hive", username=None))
    assert url == "hive://db.example.com:10000/demo"


def test_hive_with_password_keeps_password_segment(monkeypatch) -> None:
    monkeypatch.setattr(collect_service, "decrypt", lambda _enc: "secret")
    url = _build_sql_url(_source("hive", password_enc="cipher", username="hive"))
    assert url == "hive://hive:secret@db.example.com:10000/demo"


def test_password_special_chars_are_url_encoded(monkeypatch) -> None:
    monkeypatch.setattr(collect_service, "decrypt", lambda _enc: "p@ss/w:rd")
    url = _build_sql_url(_source("postgresql", password_enc="cipher", username="u"))
    assert url == "postgresql+psycopg://u:p%40ss%2Fw%3Ard@db.example.com:5432/demo"


def test_decrypt_failure_raises_collect_error(monkeypatch) -> None:
    def _boom(_enc: str) -> str:
        raise ValueError("bad key")

    monkeypatch.setattr(collect_service, "decrypt", _boom)
    with pytest.raises(CollectError, match="口令解密失败"):
        _build_sql_url(_source("mysql", password_enc="cipher", username="u"))


# ---------------------------------------------------------------- 连接参数分派


def test_connect_args_clickhouse_has_both_timeouts() -> None:
    """ClickHouse 驱动对两个超时参数都认，缺任一即报未知关键字。"""
    args = _connect_args(_source("clickhouse"))
    assert args == {
        "connect_timeout": SQL_TIMEOUT_SECONDS,
        "send_receive_timeout": SQL_TIMEOUT_SECONDS,
    }


def test_connect_args_hive_has_no_timeout_key() -> None:
    """PyHive 不接受 connect_timeout，误传会抛 TypeError。"""
    args = _connect_args(_source("hive"))
    assert args == {}
    assert "connect_timeout" not in args


def test_connect_args_hive_with_password_uses_ldap() -> None:
    args = _connect_args(_source("hive", password_enc="cipher"))
    assert args == {"auth": "LDAP"}


@pytest.mark.parametrize("ds_type", ["postgresql", "mysql"])
def test_connect_args_default_single_timeout(ds_type: str) -> None:
    assert _connect_args(_source(ds_type)) == {"connect_timeout": SQL_TIMEOUT_SECONDS}


# ---------------------------------------------------------------- 表名白名单


@pytest.mark.parametrize("table", ["ods_daily_shop", "dw.fact_orders", "t1"])
def test_table_pattern_accepts_whitelisted_names(table: str) -> None:
    assert SQL_TABLE_PATTERN.match(table)


@pytest.mark.parametrize(
    "table",
    ["ods_daily_shop; DROP TABLE x", "ods_daily_shop--", "1abc", "", "a b", "a.b.c", "tbl'"],
)
def test_table_pattern_rejects_injection(table: str) -> None:
    assert not SQL_TABLE_PATTERN.match(table)


# ---------------------------------------------------------------- SSRF 防护


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "localhost", "10.0.0.5", "192.168.1.10", "172.16.3.4", "169.254.1.1", "::1", "0.0.0.0"],
)
def test_private_or_loopback_host_rejected(host: str) -> None:
    assert _is_public_host(host) is False


@pytest.mark.parametrize("host", ["8.8.8.8", "api.example.com"])
def test_public_host_allowed(host: str) -> None:
    assert _is_public_host(host) is True


# ---------------------------------------------------------------- 记录定位


def test_extract_records_by_data_path() -> None:
    payload = {"code": 0, "data": {"items": [{"v": 1}, {"v": 2}]}}
    records = _extract_records(payload, "data.items")
    assert records == [{"v": 1}, {"v": 2}]


def test_extract_records_unwraps_single_list_field() -> None:
    payload = {"data": [{"v": 1}]}
    assert _extract_records(payload, "data") == [{"v": 1}]


def test_extract_records_missing_path_raises() -> None:
    with pytest.raises(CollectError, match="数据路径不存在"):
        _extract_records({"data": {}}, "data.items")


def test_extract_records_empty_list_raises() -> None:
    with pytest.raises(CollectError, match="为空"):
        _extract_records({"items": []}, "items")


def test_extract_records_over_limit_raises() -> None:
    payload = {"items": [{"v": i} for i in range(API_MAX_RECORDS + 1)]}
    with pytest.raises(CollectError, match="超过单次采集上限"):
        _extract_records(payload, "items")


def test_extract_records_filters_non_dict_items() -> None:
    assert _extract_records({"items": [1, {"v": 2}, "x"]}, "items") == [{"v": 2}]


# ---------------------------------------------------------------- 调度排期


def test_compute_next_run_manual_returns_none() -> None:
    assert compute_next_run(datetime(2026, 9, 30, tzinfo=timezone.utc), "manual", 5) is None


def test_compute_next_run_interval_adds_minutes() -> None:
    base = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)
    assert compute_next_run(base, "interval", 15) == base + timedelta(minutes=15)


def test_compute_next_run_rejects_below_min_interval() -> None:
    base = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)
    assert compute_next_run(base, "interval", 0) is None
