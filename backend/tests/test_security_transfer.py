"""M14 导入导出安全中心测试。

覆盖：导入 zip/tar.gz 自动解压提取、zip-slip 路径穿越防护、
普通导出、加密导出（付费插件门控）、密码加密落库、租户隔离。
"""

import io
import os
import tarfile
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import crypto as core_crypto
from app.models.base import Base
from app.models.plugin import CorePlugin
from app.models.security_transfer import ExportRecord, ImportRecord
from app.schemas.security_transfer import ExportRequest, ImportRequest
from app.services.security_transfer_service import (
    SECURE_EXPORT_PLUGIN_ID,
    SecurityTransferError,
    export_archive,
    import_archive,
    list_exports,
    list_imports,
)

# 内存库（避开 JSONB 等 PG 类型）
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ImportRecord.__table__,
            ExportRecord.__table__,
            CorePlugin.__table__,
        ],
    )
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _make_zip(path: str, files: dict[str, bytes], evil: str | None = None) -> str:
    """构造 zip；evil 为非空时注入穿越成员名。"""
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        if evil:
            zf.writestr(evil, b"evil")
    return path


def _make_tar_gz(path: str, files: dict[str, bytes]) -> str:
    with tarfile.open(path, "w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def test_import_zip_extract(db, tmp_path):
    src = _make_zip(
        str(tmp_path / "a.zip"),
        {"folder/1.txt": b"one", "2.csv": b"csv,data"},
    )
    target = tmp_path / "out"
    rec = import_archive(
        db,
        tenant_id=1,
        payload=ImportRequest(source_path=src, target_dir=str(target), archive_type="zip"),
    )
    assert rec.status == "done"
    assert rec.file_count == 2
    assert (target / "folder/1.txt").read_bytes() == b"one"
    assert (target / "2.csv").read_bytes() == b"csv,data"


def test_import_tar_gz_extract(db, tmp_path):
    src = _make_tar_gz(str(tmp_path / "b.tar.gz"), {"x/y.md": b"# hi"})
    target = tmp_path / "out2"
    rec = import_archive(
        db,
        tenant_id=1,
        payload=ImportRequest(source_path=src, target_dir=str(target), archive_type="tar.gz"),
    )
    assert rec.status == "done"
    assert rec.file_count == 1
    assert (target / "x/y.md").read_bytes() == b"# hi"


@pytest.mark.parametrize(
    "evil",
    [
        "../escape.txt",
        "../../../tmp/evil.txt",
        "/etc/passwd",
        "C:/windows/evil.txt",
        "..\\nested\\evil.txt",
    ],
)
def test_import_zip_slip_rejected(db, tmp_path, evil):
    src = _make_zip(str(tmp_path / "evil.zip"), {"ok.txt": b"ok"}, evil=evil)
    target = tmp_path / "out_evil"
    rec = import_archive(
        db,
        tenant_id=1,
        payload=ImportRequest(source_path=src, target_dir=str(target), archive_type="zip"),
    )
    assert rec.status == "failed"
    assert "拒绝" in (rec.error or "")


def test_import_missing_source(db, tmp_path):
    rec = import_archive(
        db,
        tenant_id=1,
        payload=ImportRequest(
            source_path=str(tmp_path / "nope.zip"), target_dir=str(tmp_path / "t"), archive_type="zip"
        ),
    )
    assert rec.status == "failed"
    assert "不存在" in (rec.error or "")


def test_export_plain_zip(db, tmp_path):
    src = tmp_path / "data_src"
    (src / "sub").mkdir(parents=True)
    (src / "r.txt").write_bytes(b"raw")
    (src / "sub" / "n.txt").write_bytes(b"nested")
    rec = export_archive(
        db,
        tenant_id=1,
        payload=ExportRequest(
            source_dir=str(src), target_name="plain.zip", encrypted=False
        ),
    )
    assert rec.status == "done"
    assert rec.encrypted is False
    assert rec.plugin_required is False
    assert rec.file_count == 2
    assert os.path.isfile(rec.target_path or "")
    with zipfile.ZipFile(rec.target_path) as zf:
        assert "r.txt" in zf.namelist()


def test_export_encrypted_requires_plugin(db, tmp_path):
    src = tmp_path / "sec_src"
    src.mkdir()
    (src / "s.txt").write_bytes(b"secret")
    rec = export_archive(
        db,
        tenant_id=1,
        payload=ExportRequest(
            source_dir=str(src), target_name="enc.zip", encrypted=True, password="p@ss1234"
        ),
        allow_encrypted=False,
    )
    assert rec.status == "failed"
    assert "付费插件" in (rec.error or "")


def test_export_encrypted_with_plugin(db, tmp_path):
    src = tmp_path / "sec_src2"
    src.mkdir()
    (src / "s.txt").write_bytes(b"secret-data")
    plugin = CorePlugin(
        plugin_id=SECURE_EXPORT_PLUGIN_ID,
        name="Secure Export",
        kind="official",
        version="1.0.0",
        state="enabled",
        namespace={},
    )
    db.add(plugin)
    db.commit()

    rec = export_archive(
        db,
        tenant_id=1,
        payload=ExportRequest(
            source_dir=str(src), target_name="enc2.zip", encrypted=True, password="p@ss5678"
        ),
        allow_encrypted=True,
    )
    assert rec.status == "done"
    assert rec.encrypted is True
    assert rec.plugin_required is True
    assert rec.password_ref is not None
    # 密码为密文引用，非明文
    assert "p@ss5678" not in rec.password_ref
    # 可解密还原
    assert core_crypto.decrypt(rec.password_ref) == "p@ss5678"
    # 落盘文件确为加密 zip
    with zipfile.ZipFile(rec.target_path) as zf:
        for zi in zf.infolist():
            assert zi.flag_bits & 0x1, "zip 应开启加密标志"


def test_export_encrypted_missing_password(db, tmp_path):
    src = tmp_path / "sec_src3"
    src.mkdir()
    (src / "s.txt").write_bytes(b"secret")
    with pytest.raises(SecurityTransferError):
        export_archive(
            db,
            tenant_id=1,
            payload=ExportRequest(
                source_dir=str(src), target_name="enc3.zip", encrypted=True, password=None
            ),
            allow_encrypted=True,
        )


def test_list_imports_and_exports_tenant_isolated(db, tmp_path):
    src1 = _make_zip(str(tmp_path / "t1.zip"), {"1.txt": b"1"})
    src2 = _make_zip(str(tmp_path / "t2.zip"), {"2.txt": b"2"})
    import_archive(db, tenant_id=10, payload=ImportRequest(source_path=src1, target_dir=str(tmp_path / "o1"), archive_type="zip"))
    import_archive(db, tenant_id=11, payload=ImportRequest(source_path=src2, target_dir=str(tmp_path / "o2"), archive_type="zip"))

    out10 = list_imports(db, tenant_id=10)
    out11 = list_imports(db, tenant_id=11)
    assert out10["total"] == 1
    assert out11["total"] == 1

    s1 = tmp_path / "e_src"
    s1.mkdir()
    (s1 / "a.txt").write_bytes(b"a")
    export_archive(db, tenant_id=10, payload=ExportRequest(source_dir=str(s1), target_name="e1.zip", encrypted=False))
    export_archive(db, tenant_id=11, payload=ExportRequest(source_dir=str(s1), target_name="e2.zip", encrypted=False))

    assert list_exports(db, tenant_id=10)["total"] == 1
    assert list_exports(db, tenant_id=11)["total"] == 1
