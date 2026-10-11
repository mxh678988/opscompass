"""OS 内核 · 插件私有存储门面测试（M5 剩余装配）。

覆盖：
- 引擎：写入/读取（文本、二进制）、自动建父目录、删除、列出
- 路径安全：空路径、绝对路径、.. 穿越、越界引用全部拒绝
- 插件隔离：不同插件 storage 根互不可见
- SDK storage 门面：未装配分期提示、装配后转发（save/read/delete/list）
- 运行时装配：build_context 后 ctx.storage 可用，读写落在私有根目录

无外部依赖，直接执行：``pytest tests/test_plugin_storage.py -v``。
"""

from pathlib import Path

import pytest

from app.core.plugin.registry import PluginRegistry
from app.core.plugin.runtime import PluginRuntime
from app.core.plugin.storage import PluginStorageEngine, StoragePathError
from app.sdk.exceptions import NotAvailableError


GOOD_MANIFEST = """\
id: sentiment
name: 舆情插件
version: 0.1.0
kind: community
min_kernel_version: 0.11.0
entry: main:register
namespace:
  tables: os_sentiment_
  events: "sentiment."
  permissions: "sentiment:"
permissions:
  - code: sentiment:task:create
    name: 创建舆情任务
"""


@pytest.fixture()
def storage_engine(tmp_path: Path) -> PluginStorageEngine:
    return PluginStorageEngine(tmp_path / "plugins")


@pytest.fixture()
def registry(tmp_path: Path) -> PluginRegistry:
    plugin_dir = tmp_path / "plugins" / "sentiment"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(GOOD_MANIFEST, encoding="utf-8")
    reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
    reg.register(plugin_id="sentiment")
    return reg


# ---------------- 引擎基础读写 ----------------


def test_write_and_read_text(storage_engine: PluginStorageEngine) -> None:
    storage_engine.write("demo", "cache/last.json", '{"n": 1}')
    assert storage_engine.read("demo", "cache/last.json") == '{"n": 1}'


def test_write_auto_creates_parent_dirs(storage_engine: PluginStorageEngine) -> None:
    storage_engine.write("demo", "a/b/c/data.txt", "x")
    assert storage_engine.read("demo", "a/b/c/data.txt") == "x"


def test_write_and_read_binary(storage_engine: PluginStorageEngine) -> None:
    payload = b"\x00\x01\xff"
    storage_engine.write("demo", "blob.bin", payload, binary=True)
    assert storage_engine.read("demo", "blob.bin", binary=True) == payload


def test_delete_missing_returns_false(storage_engine: PluginStorageEngine) -> None:
    assert storage_engine.delete("demo", "none.txt") is False


def test_delete_existing(storage_engine: PluginStorageEngine) -> None:
    storage_engine.write("demo", "tmp.txt", "v")
    assert storage_engine.delete("demo", "tmp.txt") is True
    assert storage_engine.list("demo") == []


def test_list_recursive_and_prefix(storage_engine: PluginStorageEngine) -> None:
    storage_engine.write("demo", "a.txt", "1")
    storage_engine.write("demo", "sub/b.txt", "2")
    storage_engine.write("demo", "sub/c.txt", "3")
    assert storage_engine.list("demo") == ["a.txt", "sub/b.txt", "sub/c.txt"]
    assert storage_engine.list("demo", prefix="sub/") == ["sub/b.txt", "sub/c.txt"]


def test_list_missing_root_returns_empty(storage_engine: PluginStorageEngine) -> None:
    assert storage_engine.list("ghost") == []


# ---------------- 路径安全 ----------------


@pytest.mark.parametrize("bad", ["", "   ", "/etc/passwd", "\\etc\\passwd", "..", "a/../../b", "a/../..", ".", "a/."])
def test_path_rejects_illegal(storage_engine: PluginStorageEngine, bad: str) -> None:
    with pytest.raises(StoragePathError):
        storage_engine.write("demo", bad, "x")


def test_path_escape_via_symlink(storage_engine: PluginStorageEngine, tmp_path: Path) -> None:
    """解析后越界的（软链指向插件根之外）必须被拒绝。"""
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    storage_engine.write("demo", "sub/dir/keep.txt", "x")  # 先建真实目录
    link = tmp_path / "plugins" / "demo" / "storage" / "sub" / "dir" / "evil.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不允许创建符号链接（需开发者模式/管理员权限）")
    with pytest.raises(StoragePathError):
        storage_engine.read("demo", "sub/dir/evil.txt")


def test_plugin_isolation(storage_engine: PluginStorageEngine) -> None:
    storage_engine.write("a", "x.txt", "aaa")
    assert storage_engine.list("b") == []
    with pytest.raises(FileNotFoundError):
        storage_engine.read("b", "x.txt")


# ---------------- SDK 门面 ----------------


def test_storage_facade_not_available_without_fn() -> None:
    from app.sdk.context import create_context

    ctx = create_context(plugin_id="demo", plugin_version="0.1.0")
    for op in (lambda: ctx.storage.save("a.txt", "x"), lambda: ctx.storage.read("a.txt")):
        with pytest.raises(NotAvailableError) as ei:
            op()
        assert "M5 装配完成" in str(ei.value)


def test_storage_facade_forwards_ops(storage_engine: PluginStorageEngine) -> None:
    from app.sdk.context import create_context

    def storage_fn(*, op: str, path: str, data=None, prefix=None):
        if op == "save":
            return storage_engine.write("demo", path, data)
        if op == "read":
            return storage_engine.read("demo", path)
        if op == "delete":
            return storage_engine.delete("demo", path)
        if op == "list":
            return storage_engine.list("demo", prefix)
        raise ValueError(op)

    ctx = create_context(plugin_id="demo", plugin_version="0.1.0", storage_fn=storage_fn)
    assert ctx.storage.save("k/v.txt", "payload") == "k/v.txt"
    assert ctx.storage.read("k/v.txt") == "payload"
    assert ctx.storage.list(prefix="k/") == ["k/v.txt"]
    assert ctx.storage.delete("k/v.txt") is True
    assert ctx.storage.list() == []


# ---------------- 运行时装配 ----------------


def test_runtime_assembles_storage(registry: PluginRegistry, tmp_path: Path) -> None:
    runtime = PluginRuntime(registry)
    ctx = runtime.build_context("sentiment")

    ctx.storage.save("state/snapshot.json", '{"ok": true}')
    assert ctx.storage.read("state/snapshot.json") == '{"ok": true}'
    assert ctx.storage.list() == ["state/snapshot.json"]

    # 落盘位置必须是插件私有根目录
    target = tmp_path / "plugins" / "sentiment" / "storage" / "state" / "snapshot.json"
    assert target.is_file()
    assert ctx.storage.delete("state/snapshot.json") is True
