"""M15 响应式网站生成器测试。

覆盖：创建/列表/详情/更新/删除、slug 唯一、host_mode 校验、
发布生成响应式 HTML（viewport、SEO meta、GEO JSON-LD）、
用户内容 HTML 转义、租户隔离。
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.site_project import SiteProject
from app.schemas.site_project import SiteProjectIn
from app.services.site_service import (
    SiteError,
    create_site,
    delete_site,
    get_preview_html,
    get_site,
    list_sites,
    publish_site,
    update_site,
)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=engine, tables=[SiteProject.__table__])
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    session.query(SiteProject).delete()
    session.commit()
    yield session
    session.rollback()
    session.close()


def _payload(**overrides):
    data = dict(
        name="老孟科技官网",
        slug="laomeng-site",
        description="响应式官网",
        seo_title="老孟科技 - 全域运营决策",
        seo_description="面向运营的决策平台",
        seo_keywords="运营,决策,AI",
        geo_enabled=True,
        geo_region="广东深圳",
        geo_org_type="Organization",
        host_mode="link",
        content={
            "sections": [
                {"type": "hero", "title": "让运营更简单", "text": "全域运营决策平台"},
                {"type": "features", "title": "核心能力", "items": [
                    {"title": "AI 洞察", "text": "自动归因"},
                    {"title": "自动执行", "text": "一句话落地"},
                ]},
                {"type": "contact", "title": "联系我们", "text": "mxh6789@live.cn"},
            ]
        },
    )
    data.update(overrides)
    return SiteProjectIn(**data)


def test_create_and_get(db):
    proj = create_site(db, 1, _payload())
    assert proj.id > 0
    assert proj.status == "draft"
    got = get_site(db, 1, proj.id)
    assert got.name == "老孟科技官网"
    assert got.slug == "laomeng-site"


def test_create_duplicate_slug(db):
    create_site(db, 1, _payload())
    with pytest.raises(SiteError, match="slug 已存在"):
        create_site(db, 1, _payload())


def test_slug_scoped_by_tenant(db):
    create_site(db, 1, _payload())
    proj2 = create_site(db, 2, _payload())
    assert proj2.id > 0


def test_invalid_host_mode(db):
    with pytest.raises(SiteError, match="host_mode"):
        create_site(db, 1, _payload(host_mode="other"))


def test_update_site(db):
    proj = create_site(db, 1, _payload())
    upd = update_site(db, 1, proj.id, SiteProjectIn(
        **{**dict(
            name="老孟科技新站",
            slug="laomeng-new",
            description="更新",
            template="default",
            geo_enabled=False,
            host_mode="space",
            content={"sections": []},
        )}
    ))
    assert upd.name == "老孟科技新站"
    assert upd.slug == "laomeng-new"
    assert upd.host_mode == "space"


def test_delete_site(db):
    proj = create_site(db, 1, _payload())
    delete_site(db, 1, proj.id)
    with pytest.raises(SiteError, match="不存在"):
        get_site(db, 1, proj.id)


def test_publish_generates_responsive_html(db):
    proj = create_site(db, 1, _payload())
    pub = publish_site(db, 1, proj.id)
    assert pub.status == "published"
    assert pub.publish_path and pub.publish_path.endswith("index.html")
    import os

    assert os.path.exists(pub.publish_path)
    html_doc = open(pub.publish_path, encoding="utf-8").read()
    # 移动优先
    assert '<meta name="viewport"' in html_doc
    assert "@media (max-width:768px)" in html_doc
    # SEO meta
    assert "老孟科技 - 全域运营决策" in html_doc
    assert '<meta name="keywords"' in html_doc
    # GEO JSON-LD
    assert '"@context": "https://schema.org"' in html_doc
    assert '"addressRegion": "广东深圳"' in html_doc
    # 内容渲染
    assert "让运营更简单" in html_doc
    assert "AI 洞察" in html_doc


def test_preview_html(db):
    proj = create_site(db, 1, _payload())
    html_doc = get_preview_html(db, 1, proj.id)
    assert "让运营更简单" in html_doc


def test_html_escape_user_content(db):
    proj = create_site(db, 1, _payload(content={
        "sections": [
            {"type": "hero", "title": "<script>alert(1)</script>", "text": "x"},
        ]
    }))
    html_doc = get_preview_html(db, 1, proj.id)
    assert "<script>alert(1)</script>" not in html_doc
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_doc


def test_tenant_isolation(db):
    p1 = create_site(db, 1, _payload())
    with pytest.raises(SiteError, match="不存在"):
        get_site(db, 2, p1.id)
    assert list_sites(db, 2) == []
    assert len(list_sites(db, 1)) == 1


def test_invalid_slug_pattern():
    with pytest.raises(Exception):
        _payload(slug="bad slug!")
