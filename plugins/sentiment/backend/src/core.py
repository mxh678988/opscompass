"""舆情监控核心引擎 - 数据模型与业务逻辑。

本模块提供采集、情感分析、事件归并、预警、分析、报告生成等核心能力，
供 PluginRuntime 注入到 PluginContext.sentiment 中。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from .database import (
    Base,
    SentimentTopic,
    SentimentSource,
    SentimentTask,
    SentimentItem,
    SentimentEmotion,
    SentimentEntity,
    SentimentEvent,
    SentimentEventItem,
    SentimentAlertRule,
    SentimentAlert,
    SentimentReport,
    SentimentKeywordStat,
)
from sqlalchemy.orm import Session
import random

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 情感分析规则引擎
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> dict[str, Any]:
    """规则预筛情感分析：快速判断正/中/负。

    返回 {polarity, intensity, confidence}。
    本 MVP 使用规则预筛，完整版接入本地 LLM 模型。
    """
    if not text or len(text) < 2:
        return {"polarity": "neutral", "intensity": 3, "confidence": 0}

    pos_words = ["好", "棒", "优秀", "喜欢", "满意", "赞", "完美", "推荐", "方便", "快",
                 "great", "good", "like", "love", "perfect", "excellent", "awesome"]
    neg_words = ["差", "烂", "垃圾", "失望", "慢", "贵", "不好", "坑", "骗", "坏",
                 "bad", "terrible", "hate", "poor", "worst", "awful"]

    pos_count = sum(1 for w in pos_words if w in text)
    neg_count = sum(1 for w in neg_words if w in text)
    total = pos_count + neg_count
    confidence = min(total, 10)

    if pos_count > neg_count and pos_count >= 2:
        polarity = "positive"
        intensity = min(5, 3 + pos_count - neg_count)
    elif neg_count > pos_count and neg_count >= 2:
        polarity = "negative"
        intensity = min(5, 3 + neg_count - pos_count)
    else:
        polarity = "neutral"
        intensity = 3

    return {"polarity": polarity, "intensity": intensity, "confidence": confidence}


# ---------------------------------------------------------------------------
# 实体识别（MVP：简单关键词匹配）
# ---------------------------------------------------------------------------

def extract_entities(text: str, topics: list) -> list[dict[str, str]]:
    """从文本中提取实体（品牌、竞品、产品等）。"""
    entities = []
    for topic in topics:
        keywords = topic.get("keywords", [])
        for kw in keywords:
            if kw in text:
                entities.append({
                    "entity_type": "keyword",
                    "entity_name": kw,
                    "confidence": 80,
                })
    return entities


# ---------------------------------------------------------------------------
# 指纹计算
# ---------------------------------------------------------------------------

def compute_fingerprint(text: str) -> str:
    """计算内容指纹（基于标题+正文前200字）。"""
    content = (text[:200]).lower().replace("\n", "").replace("\r", "").strip()
    return hashlib.md5(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 舆情引擎核心
# ---------------------------------------------------------------------------

class SentimentEngine:
    """舆情监控引擎。"""

    def __init__(self, db: Session, plugin_id: str):
        self.db = db
        self.plugin_id = plugin_id
        self._topics: list[dict] = []
        self._sources: list[dict] = []
        self._load_metadata()

    def _load_metadata(self) -> None:
        """加载主题和数据源元数据。"""
        self._topics = [
            {
                "id": r.id,
                "name": r.name,
                "keywords": r.keywords or [],
                "brand_entities": r.brand_entities or [],
                "product_line": r.product_line or "",
                "exclude_keywords": r.exclude_keywords or [],
            }
            for r in self.db.query(SentimentTopic).filter_by(plugin_id=self.plugin_id).all()
        ]
        self._sources = [
            {
                "id": r.id,
                "source_type": r.source_type,
                "access_type": r.access_type,
                "topic_id": r.topic_id,
            }
            for r in self.db.query(SentimentSource).filter_by(plugin_id=self.plugin_id).all()
        ]

    # -------------------------------------------------------------------
    # FR-S-201: 采集
    # -------------------------------------------------------------------
    def monitor(self, topic_id: str, source_id: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        """采集舆情条目。

        参数：
            topic_id: 主题 ID
            source_id: 数据源 ID（可选）
            **kwargs: 额外采集参数

        返回：
            {fetched, inserted, failed, errors}
        """
        topic = next((t for t in self._topics if t["id"] == topic_id), None)
        if not topic:
            return {"fetched": 0, "inserted": 0, "failed": 0, "errors": [f"主题不存在: {topic_id}"]}

        source = None
        if source_id:
            source = next((s for s in self._sources if s["id"] == source_id), None)

        # 模拟采集（MVP）：生成测试数据
        fetched = 0
        inserted = 0
        failed = 0
        errors = []

        try:
            # 模拟从数据源采集（实际应调用采集器）
            # 这里生成示例数据用于测试
            sample_titles = [
                f"关于{topic['name']}的用户反馈第{i+1}期",
                f"{topic['name']}最新动态 - 第{i+1}条",
            ]

            for i in range(5):  # 模拟采集5条
                title = random.choice(sample_titles).format()
                content = f"用户对{topic['name']}的评价：{random.choice(['很好', '不错', '一般', '差劲', '完美', '失望'])}"

                item = SentimentItem(
                    plugin_id=self.plugin_id,
                    topic_id=topic_id,
                    source_id=source_id or "",
                    title=title,
                    content=content,
                    author=f"用户{random.randint(1000, 9999)}",
                    author_fans=random.randint(0, 100000),
                    publish_at=datetime.utcnow(),
                    url=f"https://example.com/post/{uuid4().hex[:8]}",
                    fingerprint=compute_fingerprint(content),
                    lang="zh",
                    raw={"source": "simulated"},
                )
                self.db.add(item)
                self.db.flush()  # 获取 ID

                # 情感分析
                sentiment = analyze_sentiment(content)
                emotion = SentimentEmotion(
                    plugin_id=self.plugin_id,
                    item_id=item.id,
                    polarity=sentiment["polarity"],
                    intensity=sentiment["intensity"],
                    model="rule",
                    rule_hit=True,
                    confidence=sentiment["confidence"],
                    labeled_at=datetime.utcnow(),
                )
                self.db.add(emotion)

                # 实体识别
                entities = extract_entities(content, [topic])
                for entity in entities:
                    entity_record = SentimentEntity(
                        plugin_id=self.plugin_id,
                        item_id=item.id,
                        entity_type=entity["entity_type"],
                        entity_name=entity["entity_name"],
                        confidence=entity["confidence"],
                    )
                    self.db.add(entity_record)

                fetched += 1
                inserted += 1

            self.db.commit()

            # 发布采集事件
            try:
                self._publish_event("sentiment.item.collected", {
                    "topic_id": topic_id,
                    "source_id": source_id,
                    "fetched": fetched,
                    "inserted": inserted,
                })
            except Exception:
                pass

        except Exception as e:
            failed = fetched - inserted
            errors.append(str(e))
            self.db.rollback()

        # 更新采集任务记录
        task = SentimentTask(
            plugin_id=self.plugin_id,
            source_id=source_id or "",
            trigger_type="manual",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            fetched=fetched,
            inserted=inserted,
            failed=failed,
        )
        self.db.add(task)
        self.db.commit()

        return {
            "fetched": fetched,
            "inserted": inserted,
            "failed": failed,
            "errors": errors,
        }

    # -------------------------------------------------------------------
    # FR-S-204: 情感分析
    # -------------------------------------------------------------------
    def analyze(self, item_id: str, **kwargs: Any) -> dict[str, Any]:
        """对单条条目执行情感分析 + 实体识别。

        返回：{polarity, intensity, confidence, entities}
        """
        item = self.db.query(SentimentItem).filter_by(id=item_id).first()
        if not item:
            return {"error": f"条目不存在: {item_id}"}

        sentiment = analyze_sentiment(item.content)
        topic = next((t for t in self._topics if t["id"] == item.topic_id), {})
        entities = extract_entities(item.content, [topic])

        return {
            "polarity": sentiment["polarity"],
            "intensity": sentiment["intensity"],
            "confidence": sentiment["confidence"],
            "entities": entities,
        }

    # -------------------------------------------------------------------
    # FR-S-203: 事件归并
    # -------------------------------------------------------------------
    def merge_event(self, item_ids: list[str], **kwargs: Any) -> dict[str, Any]:
        """将多条条目归并为一个事件。

        返回：{event_id, title, item_count}
        """
        items = self.db.query(SentimentItem).filter(SentimentItem.id.in_(item_ids)).all()
        if not items:
            return {"error": "未找到指定条目"}

        topic_id = items[0].topic_id
        # 取第一条的标题作为事件标题
        title = items[0].title or f"事件 - {topic_id} - {datetime.utcnow().strftime('%Y-%m-%d')}"

        # 生成事件
        event_id = str(uuid4())
        event = SentimentEvent(
            plugin_id=self.plugin_id,
            topic_id=topic_id,
            title=title,
            first_seen_at=min(i.publish_at for i in items if i.publish_at),
            item_count=len(items),
            status="active",
        )
        self.db.add(event)

        # 关联条目
        for item in items:
            event_item = SentimentEventItem(
                plugin_id=self.plugin_id,
                event_id=event_id,
                item_id=item.id,
                relation_role="republish",  # 默认关系
            )
            self.db.add(event_item)

        self.db.commit()

        # 发布事件创建事件
        try:
            self._publish_event("sentiment.event.created", {
                "event_id": event_id,
                "topic_id": topic_id,
                "title": title,
                "item_count": len(items),
            })
        except Exception:
            pass

        return {
            "event_id": event_id,
            "title": title,
            "item_count": len(items),
            "topic_id": topic_id,
        }

    # -------------------------------------------------------------------
    # FR-S-401: 预警规则检查
    # -------------------------------------------------------------------
    def check_alert(self, event_id: str, **kwargs: Any) -> dict[str, Any]:
        """对事件执行预警规则检查，返回命中的规则与定级。

        返回：{alerts: [{rule_id, rule_type, level, hit_detail}], event_level}
        """
        event = self.db.query(SentimentEvent).filter_by(id=event_id).first()
        if not event:
            return {"error": f"事件不存在: {event_id}"}

        # 获取该事件相关的预警规则
        rules = self.db.query(SentimentAlertRule).filter_by(topic_id=event.topic_id).all()

        alerts = []
        for rule in rules:
            if not rule.enabled:
                continue

            # 简单规则检查（MVP）
            hit = False
            detail = {}

            if rule.rule_type == "volume_surge":
                # 量级突增
                count = event.item_count
                params = rule.params or {}
                threshold = params.get("threshold", 100)
                if count >= threshold:
                    hit = True
                    detail = {"current_count": count, "threshold": threshold}

            elif rule.rule_type == "negative_ratio":
                # 负向占比超阈
                # 获取该事件下所有情感分析结果
                emotions = self.db.query(SentimentEmotion).join(SentimentEventItem).filter(
                    SentimentEventItem.event_id == event_id,
                    SentimentEmotion.polarity == "negative"
                ).all()
                total_emotions = self.db.query(SentimentEmotion).join(SentimentEventItem).filter(
                    SentimentEventItem.event_id == event_id
                ).count()
                if total_emotions > 0:
                    neg_ratio = len(emotions) / total_emotions
                    params = rule.params or {}
                    threshold = params.get("threshold", 0.5)
                    if neg_ratio >= threshold:
                        hit = True
                        detail = {"negative_ratio": neg_ratio, "threshold": threshold}

            elif rule.rule_type == "sensitive_word":
                # 敏感词命中
                params = rule.params or {}
                sensitive_words = params.get("words", [])
                # 简化：假设已内置敏感词
                for word in sensitive_words:
                    if word in event.title:
                        hit = True
                        detail = {"sensitive_word": word}
                        break

            if hit:
                alert = SentimentAlert(
                    plugin_id=self.plugin_id,
                    rule_id=rule.id,
                    event_id=event_id,
                    level=rule.level,
                    status="pending",
                    hit_detail=detail,
                )
                self.db.add(alert)
                alerts.append({
                    "rule_id": rule.id,
                    "rule_type": rule.rule_type,
                    "level": rule.level,
                    "hit_detail": detail,
                })

        # 确定事件等级（取最高）
        level_order = {"S1": 1, "S2": 2, "S3": 3, "S4": 4}
        event_level = "S4"  # 默认最低
        for a in alerts:
            if level_order.get(a["level"], 4) < level_order.get(event_level, 4):
                event_level = a["level"]

        self.db.commit()

        # 发布预警事件
        if alerts:
            try:
                self._publish_event("sentiment.alert.created", {
                    "event_id": event_id,
                    "alerts": alerts,
                    "event_level": event_level,
                })
            except Exception:
                pass

        return {
            "alerts": alerts,
            "event_level": event_level,
            "event_id": event_id,
        }

    # -------------------------------------------------------------------
    # FR-S-300: 分析
    # -------------------------------------------------------------------
    def get_analytics(self, topic_id: str, period: str = "7d", **kwargs: Any) -> dict[str, Any]:
        """获取舆情分析数据。

        返回：{hot_heat, emotion, trend, benchmark}
        """
        # 计算时间范围
        days = int(period.replace("d", ""))
        start_date = datetime.utcnow() - timedelta(days=days)

        # 热度数据
        items = self.db.query(SentimentItem).filter(
            SentimentItem.topic_id == topic_id,
            SentimentItem.publish_at >= start_date
        ).all()

        # 情绪结构
        positive = sum(1 for i in items if i.status == "positive")
        neutral = sum(1 for i in items if i.status == "neutral")
        negative = sum(1 for i in items if i.status == "negative")
        total = len(items)

        # 竞品对标
        benchmark = {
            "our_sentiment": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "total": total,
            },
            "competitors": [],  # 简化处理
        }

        return {
            "hot_heat": {
                "total_items": total,
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
            },
            "emotion": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "total": total,
            },
            "trend": [
                {
                    "date": (start_date + timedelta(days=i)).isoformat(),
                    "count": random.randint(10, 50),
                }
                for i in range(days)
            ],
            "benchmark": benchmark,
        }

    # -------------------------------------------------------------------
    # FR-S-500: 报告生成
    # -------------------------------------------------------------------
    def generate_report(self, topic_id: str, report_type: str = "daily", **kwargs: Any) -> dict[str, Any]:
        """生成报告。

        返回：{report_id, preview, file_path}
        """
        # 计算报告周期
        if report_type == "daily":
            days = 1
        elif report_type == "weekly":
            days = 7
        else:
            days = 7

        start_date = datetime.utcnow() - timedelta(days=days)

        # 获取数据
        analytics = self.get_analytics(topic_id, f"{days}d")

        # 生成报告内容
        report_content = f"""
# 舆情分析报告 - {topic_id}

**报告周期**: {start_date.strftime('%Y-%m-%d')} 至 {datetime.utcnow().strftime('%Y-%m-%d')}
**报告类型**: {report_type}
**生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

---

## 一、概览

- 总条目数: {analytics['emotion']['total']}
- 正面: {analytics['emotion']['positive']}
- 中性: {analytics['emotion']['neutral']}
- 负面: {analytics['emotion']['negative']}
- 负面率: {analytics['emotion']['negative'] / max(1, analytics['emotion']['total']) * 100:.1f}%

## 二、趋势分析

| 日期 | 条目数 |
|------|--------|
"""

        for item in analytics['trend']:
            report_content += f"| {item['date'][:10]} | {item['count']} |\n"

        report_content += """
---

**本报告由 AI 生成，仅供参考**
"""

        # 保存报告
        report_id = str(uuid4())
        file_path = f"reports/{topic_id}/{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"

        report = SentimentReport(
            plugin_id=self.plugin_id,
            topic_id=topic_id,
            report_type=report_type,
            period_start=start_date,
            period_end=datetime.utcnow(),
            content=report_content,
            ai_generated=True,
            confirmed_by="",  # 未确认
            file_path=file_path,
        )
        self.db.add(report)
        self.db.commit()

        return {
            "report_id": report_id,
            "preview": report_content[:500],
            "file_path": file_path,
        }

    # -------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------
    def _publish_event(self, name: str, payload: dict) -> str:
        """发布事件（通过 SDK 的 bus.publish）。"""
        from app.core.event_bus import EventBus
        bus = EventBus()
        return bus.publish(name, payload, plugin_id=self.plugin_id)

    def get_alerts(self, topic_id: str, status: str = "pending", **kwargs: Any) -> list[dict[str, Any]]:
        """获取预警列表。"""
        alerts = self.db.query(SentimentAlert).join(SentimentEvent).filter(
            SentimentEvent.topic_id == topic_id,
            SentimentAlert.status == status
        ).all()

        return [
            {
                "id": a.id,
                "rule_id": a.rule_id,
                "event_id": a.event_id,
                "level": a.level,
                "status": a.status,
                "hit_detail": a.hit_detail,
            }
            for a in alerts
        ]

    def get_events(self, topic_id: str, status: str = "active", **kwargs: Any) -> list[dict[str, Any]]:
        """获取事件列表。"""
        events = self.db.query(SentimentEvent).filter(
            SentimentEvent.topic_id == topic_id,
            SentimentEvent.status == status
        ).all()

        return [
            {
                "id": e.id,
                "title": e.title,
                "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
                "item_count": e.item_count,
                "spread_level": e.spread_level,
                "status": e.status,
            }
            for e in events
        ]

    def create_topic(self, name: str, keywords: list[str], brand_entities: list[str] = None, product_line: str = "") -> dict[str, Any]:
        """创建监测主题。"""
        topic = SentimentTopic(
            plugin_id=self.plugin_id,
            name=name,
            keywords=keywords,
            brand_entities=brand_entities or [],
            product_line=product_line,
            status="active",
        )
        self.db.add(topic)
        self.db.commit()
        return {"id": topic.id, "name": name}

    def create_source(self, topic_id: str, source_type: str, access_type: str = "api", endpoint: str = "", credential_ref: str = "", interval_min: int = 60, rate_limit: int = 1000) -> dict[str, Any]:
        """创建数据源配置。"""
        source = SentimentSource(
            plugin_id=self.plugin_id,
            topic_id=topic_id,
            source_type=source_type,
            access_type=access_type,
            endpoint=endpoint,
            credential_ref=credential_ref,
            interval_min=interval_min,
            rate_limit=rate_limit,
            status="active",
        )
        self.db.add(source)
        self.db.commit()
        return {"id": source.id, "source_type": source_type}

    def create_alert_rule(self, topic_id: str, rule_type: str, params: dict, level: str = "S3", silence_window: int = 0, enabled: bool = True) -> dict[str, Any]:
        """创建预警规则。"""
        rule = SentimentAlertRule(
            plugin_id=self.plugin_id,
            topic_id=topic_id,
            rule_type=rule_type,
            params=params,
            level=level,
            silence_window=silence_window,
            enabled=enabled,
        )
        self.db.add(rule)
        self.db.commit()
        return {"id": rule.id, "rule_type": rule_type, "level": level}


# ---------------------------------------------------------------------------
# 引擎工厂
# ---------------------------------------------------------------------------

def create_for_plugin(
    db: Session,
    plugin_id: str,
    action: str,
    params: Optional[dict] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """引擎工厂函数：供 PluginRuntime 注入时使用。

    参数：
        db: 数据库会话
        plugin_id: 插件 ID
        action: 动作类型（monitor/analyze/merge_event/check_alert/get_analytics/generate_report）
        params: 动作参数
        **kwargs: 额外参数

    返回：动作执行结果
    """
    engine = SentimentEngine(db, plugin_id)

    action_map = {
        "monitor": engine.monitor,
        "analyze": engine.analyze,
        "merge_event": engine.merge_event,
        "check_alert": engine.check_alert,
        "get_analytics": engine.get_analytics,
        "generate_report": engine.generate_report,
        "get_alerts": engine.get_alerts,
        "get_events": engine.get_events,
        "create_topic": engine.create_topic,
        "create_source": engine.create_source,
        "create_alert_rule": engine.create_alert_rule,
    }

    handler = action_map.get(action)
    if not handler:
        return {"error": f"未知动作: {action}"}

    return handler(**(params or {}), **kwargs)
