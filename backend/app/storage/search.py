"""全文检索适配器：PostgreSQL tsvector + GIN 索引（pg_trgm 可选增强）。

封装为可替换适配器：
- 读写统一走 search/upsert_documents/delete_documents 接口，底层表结构对上层透明；
- 能力探测（capabilities）报告 tsvector 与 pg_trgm 可用性，缺扩展时自动退化为 ILIKE 匹配；
- 中文检索：tsvector 使用 simple 配置（无中文分词），配合 pg_trgm 相似度与 ILIKE 命中中文短语。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import text

from app.storage.base import AdapterCapability

logger = logging.getLogger(__name__)

DOC_TABLE = "oc_doc_index"


class FullTextSearchAdapter:
    """全文检索适配器。"""

    kind = "fulltext"
    engine = "postgresql_gin"
    label = "全文检索索引"

    # ------------------------------------------------------------ 能力
    def capabilities(self, db) -> dict:
        caps = {"tsvector": False, "gin": False, "pg_trgm": False, "table": False}
        if db is None:
            return caps
        try:
            caps["table"] = bool(
                db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": DOC_TABLE}).scalar()
            )
            extensions = {
                r[0] for r in db.execute(text("SELECT extname FROM pg_extension")).all()
            }
            caps["tsvector"] = caps["table"]
            caps["pg_trgm"] = "pg_trgm" in extensions
            if caps["table"]:
                caps["gin"] = bool(
                    db.execute(
                        text(
                            "SELECT count(*) FROM pg_indexes WHERE tablename = :t "
                            "AND indexdef ILIKE '%USING gin%'"
                        ),
                        {"t": DOC_TABLE},
                    ).scalar()
                )
        except Exception as exc:
            logger.warning("search capabilities failed: %s", exc)
        return caps

    def _trgm_enabled(self, db) -> bool:
        return bool(self.capabilities(db).get("pg_trgm"))

    # ------------------------------------------------------------ 写入
    @staticmethod
    def _tsv_source(title: str, content: Optional[str], keywords: Optional[str]) -> str:
        return " ".join(x for x in (title or "", content or "", keywords or "") if x)

    def upsert_documents(self, db, docs: list[dict]) -> int:
        """写入/更新检索文档。docs: tenant_id/doc_type/doc_id/title/content/keywords/url/payload。"""
        if not docs:
            return 0
        sql = text(
            f"""
            INSERT INTO {DOC_TABLE}
                (tenant_id, doc_type, doc_id, title, content, keywords, url, payload, tsv, indexed_at)
            VALUES
                (:tenant_id, :doc_type, :doc_id, :title, :content, :keywords, :url,
                 CAST(:payload AS JSONB),
                 to_tsvector('simple', :tsv_source), now())
            ON CONFLICT (doc_type, doc_id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                keywords = EXCLUDED.keywords,
                url = EXCLUDED.url,
                payload = EXCLUDED.payload,
                tsv = EXCLUDED.tsv,
                indexed_at = now()
            """
        )
        payload = []
        for doc in docs:
            title = doc.get("title") or ""
            content = doc.get("content") or ""
            keywords = doc.get("keywords") or ""
            payload.append(
                {
                    "tenant_id": doc["tenant_id"],
                    "doc_type": doc["doc_type"],
                    "doc_id": str(doc["doc_id"]),
                    "title": title[:255],
                    "content": content,
                    "keywords": keywords[:512],
                    "url": (doc.get("url") or None),
                    "payload": None
                    if doc.get("payload") is None
                    else json.dumps(doc["payload"], ensure_ascii=False, default=str),
                    "tsv_source": self._tsv_source(title, content, keywords)[:20000],
                }
            )
        db.execute(sql, payload)
        db.commit()
        return len(payload)

    def delete_documents(self, db, doc_type: str, doc_ids: Optional[list[str]] = None) -> int:
        """删除检索文档（doc_ids 为空则删除该类型全部）。"""
        if doc_ids:
            result = db.execute(
                text(f"DELETE FROM {DOC_TABLE} WHERE doc_type = :dt AND doc_id = ANY(:ids)"),
                {"dt": doc_type, "ids": [str(i) for i in doc_ids]},
            )
        else:
            result = db.execute(text(f"DELETE FROM {DOC_TABLE} WHERE doc_type = :dt"), {"dt": doc_type})
        db.commit()
        return int(result.rowcount or 0)

    # ------------------------------------------------------------ 检索
    def search(
        self,
        db,
        tenant_id: int,
        q: str,
        doc_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        keyword = (q or "").strip()
        if not keyword:
            return []
        trgm = self._trgm_enabled(db)
        rank_expr = "ts_rank(tsv, plainto_tsquery('simple', :q))"
        if trgm:
            rank_expr += (
                " + similarity(coalesce(title, ''), :q) * 2.0"
                " + similarity(coalesce(content, ''), :q)"
                " + similarity(coalesce(keywords, ''), :q)"
            )
        conditions = [
            "tenant_id = :tenant_id",
            "(tsv @@ plainto_tsquery('simple', :q)"
            " OR title ILIKE :like OR coalesce(content, '') ILIKE :like"
            " OR coalesce(keywords, '') ILIKE :like)",
        ]
        if trgm:
            conditions.append("(title % :q OR tsv @@ plainto_tsquery('simple', :q) OR COALESCE(content,'') % :q)")
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "q": keyword,
            "like": f"%{keyword}%",
            "limit": int(limit),
        }
        group_by = (
            " GROUP BY id, tenant_id, doc_type, doc_id, title, content, keywords, url, indexed_at, tsv"
        )
        sql = text(
            f"SELECT id, doc_type, doc_id, title, content, keywords, url, payload, indexed_at,"
            f" {rank_expr} AS rank FROM {DOC_TABLE}"
            f" WHERE {' AND '.join(conditions)}{group_by}"
            f" ORDER BY rank DESC, indexed_at DESC LIMIT :limit"
        )
        rows = db.execute(sql, params).all()
        results = []
        for r in rows:
            item = dict(r._mapping)
            item["rank"] = float(item.get("rank") or 0.0)
            if item.get("indexed_at") is not None:
                item["indexed_at"] = item["indexed_at"].strftime("%Y-%m-%d %H:%M:%S")
            results.append(item)
        return results

    # ------------------------------------------------------------ 重建索引
    def reindex(self, db, tenant_id: Optional[int] = None, scope: Optional[list[str]] = None) -> dict:
        """从源表重建检索索引（仅补写，不删除源表已有数据）。"""
        from app.models.datasource import DataSource
        from app.models.metric import Metric, MetricCategory

        scopes = scope or ["metric", "datasource", "category"]
        written: dict[str, int] = {}
        docs: list[dict] = []

        if "metric" in scopes:
            query = db.query(Metric)
            if tenant_id is not None:
                query = query.filter(Metric.tenant_id == tenant_id)
            for m in query.all():
                docs.append(
                    {
                        "tenant_id": m.tenant_id,
                        "doc_type": "metric",
                        "doc_id": str(m.id),
                        "title": f"{m.name}({m.code})",
                        "content": " ".join(
                            x for x in [m.description or "", m.formula or "", m.unit or ""] if x
                        ),
                        "keywords": " ".join(
                            [m.code, m.name, m.metric_type, m.status, m.agg_func, *(m.tags or [])]
                        ),
                        "url": f"/metrics/{m.code}",
                        "payload": {"code": m.code, "status": m.status, "owner": m.owner},
                    }
                )
            written["metric"] = len(docs)

        if "datasource" in scopes:
            start = len(docs)
            query = db.query(DataSource)
            if tenant_id is not None:
                query = query.filter(DataSource.tenant_id == tenant_id)
            for ds in query.all():
                docs.append(
                    {
                        "tenant_id": ds.tenant_id,
                        "doc_type": "datasource",
                        "doc_id": str(ds.id),
                        "title": f"{ds.name}({ds.code})",
                        "content": f"{ds.ds_type} {ds.host or ''} {ds.db_name or ''}".strip(),
                        "keywords": " ".join([ds.code, ds.name, ds.ds_type, ds.status]),
                        "url": f"/datasources/{ds.code}",
                        "payload": {"code": ds.code, "ds_type": ds.ds_type},
                    }
                )
            written["datasource"] = len(docs) - start

        if "category" in scopes:
            start = len(docs)
            query = db.query(MetricCategory)
            if tenant_id is not None:
                query = query.filter(MetricCategory.tenant_id == tenant_id)
            for cat in query.all():
                docs.append(
                    {
                        "tenant_id": cat.tenant_id,
                        "doc_type": "category",
                        "doc_id": str(cat.id),
                        "title": f"{cat.name}({cat.code})",
                        "content": "指标分类",
                        "keywords": f"{cat.code} {cat.name}",
                        "url": None,
                        "payload": {"code": cat.code},
                    }
                )
            written["category"] = len(docs) - start

        indexed = self.upsert_documents(db, docs) if docs else 0
        return {"indexed": indexed, "by_type": written}

    # ------------------------------------------------------------ 状态
    def capability(self, db=None) -> AdapterCapability:
        caps = self.capabilities(db) if db is not None else {}
        available = bool(caps.get("table"))
        return AdapterCapability(
            kind=self.kind,
            engine=self.engine,
            label=self.label,
            available=available,
            detail={
                "table": DOC_TABLE,
                "tsvector": caps.get("tsvector", False),
                "gin_index": caps.get("gin", False),
                "pg_trgm": caps.get("pg_trgm", False),
                "fallback": None if caps.get("pg_trgm") else "pg_trgm 不可用时退化为 ILIKE 匹配",
            },
        )

    def stats(self, db=None) -> dict:
        by_type: dict[str, int] = {}
        total = 0
        size = ""
        if db is not None:
            try:
                total = int(db.execute(text(f"SELECT count(*) FROM {DOC_TABLE}")).scalar() or 0)
                rows = db.execute(
                    text(f"SELECT doc_type, count(*) AS c FROM {DOC_TABLE} GROUP BY doc_type ORDER BY doc_type")
                ).all()
                by_type = {r[0]: int(r[1]) for r in rows}
                size = str(
                    db.execute(
                        text("SELECT pg_size_pretty(pg_total_relation_size(:t))"), {"t": DOC_TABLE}
                    ).scalar()
                    or ""
                )
            except Exception as exc:
                logger.warning("search stats failed: %s", exc)
        return {
            "kind": self.kind,
            "engine": self.engine,
            "table": DOC_TABLE,
            "documents": total,
            "by_type": by_type,
            "total_size": size,
        }


search_adapter = FullTextSearchAdapter()
