"""M16 网站资源管理器测试。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.site_project import SiteProject
from app.models.site_resource import SiteResource
from app.services import site_resource_service as svc
from app.services.site_resource_service import SiteResourceError

TEST_DATA = Path(__file__).resolve().parent.parent / "data" / "sites"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
    )
    Base.metadata.create_all(bind=eng, tables=[SiteProject.__table__, SiteResource.__table__])
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def clean_data(session):
    session.query(SiteResource).delete()
    session.query(SiteProject).delete()
    session.commit()


@pytest.fixture
def published_project(session, tmp_path):
    pub = tmp_path / "public"
    (pub / "css").mkdir(parents=True)
    (pub / "img").mkdir()
    (pub / "css" / "style.css").write_text("body{color:#111}", encoding="utf-8")
    (pub / "index.html").write_text("<html><body>hi</body></html>", encoding="utf-8")
    (pub / "img" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    proj = SiteProject(
        tenant_id=1, slug="res-site", name="资源测试站",
        seo_title="资源测试站", status="published", publish_path=str(pub / "index.html"),
        host_mode="space",
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    yield proj
    shutil.rmtree(pub, ignore_errors=True)


def test_scan_creates_index(session, published_project):
    result = svc.scan_project(session, 1, published_project.id)
    assert result["scanned"] == 3
    assert result["created"] == 3
    rows = svc.list_resources(session, 1, project_id=published_project.id)
    types = {r.resource_type for r in rows}
    assert types == {"page", "css", "image"}
    for r in rows:
        assert r.checksum and len(r.checksum) == 64
        assert r.status == "active"


def test_scan_is_idempotent(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    result = svc.scan_project(session, 1, published_project.id)
    assert result["created"] == 0
    assert result["updated"] == 3
    assert result["marked_missing"] == 0


def test_scan_marks_missing(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    pub = Path(published_project.publish_path).parent
    (pub / "index.html").unlink()
    result = svc.scan_project(session, 1, published_project.id)
    assert result["marked_missing"] == 1
    missing = [r for r in svc.list_resources(session, 1, project_id=published_project.id, status="missing")]
    assert len(missing) == 1
    assert missing[0].path == "index.html"


def test_summary_counts(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    s = svc.summary(session, 1, project_id=published_project.id)
    assert s["total"] == 3
    assert s["by_type"]["page"] == 1
    assert s["by_type"]["image"] == 1
    assert s["total_size_bytes"] > 0


def test_update_resource(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    res = svc.list_resources(session, 1, project_id=published_project.id)[0]
    updated = svc.update_resource(
        session, 1, res.id, type("P", (), {"model_dump": lambda self, **k: {"status": "archived", "meta": {"tag": "x"}}})()
    )
    assert updated.status == "archived"
    assert '"tag"' in (updated.meta or "")


def test_update_invalid_status(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    res = svc.list_resources(session, 1, project_id=published_project.id)[0]
    with pytest.raises(SiteResourceError):
        svc.update_resource(
            session, 1, res.id, type("P", (), {"model_dump": lambda self, **k: {"status": "bogus"}})()
        )


def test_delete_record_only(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    res = svc.list_resources(session, 1, project_id=published_project.id)[0]
    full = Path(published_project.publish_path).parent / res.path.replace("/", os.sep)
    assert full.exists()
    svc.delete_resource(session, 1, res.id, force=False)
    assert full.exists()
    remaining = svc.list_resources(session, 1, project_id=published_project.id)
    assert len(remaining) == 2


def test_delete_force_removes_file(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    res = svc.list_resources(session, 1, project_id=published_project.id)[0]
    full = Path(published_project.publish_path).parent / res.path.replace("/", os.sep)
    assert full.exists()
    svc.delete_resource(session, 1, res.id, force=True)
    assert not full.exists()


def test_path_traversal_rejected(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    res = svc.list_resources(session, 1, project_id=published_project.id)[0]
    # 伪造一个越界路径资源，物理删除应被拒绝
    res.path = "../../outside.txt"
    session.commit()
    with pytest.raises(SiteResourceError):
        svc.delete_resource(session, 1, res.id, force=True)


def test_tenant_isolation(session, published_project):
    svc.scan_project(session, 1, published_project.id)
    assert svc.list_resources(session, 2, project_id=published_project.id) == []


def test_scan_unpublished_raises(session):
    proj = SiteProject(
        tenant_id=1, slug="no-pub", name="未发布站", seo_title="未发布站",
        status="draft", host_mode="link",
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    with pytest.raises(SiteResourceError):
        svc.scan_project(session, 1, proj.id)
