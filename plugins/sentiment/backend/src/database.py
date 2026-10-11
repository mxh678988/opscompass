import uuid
from datetime import datetime

from app.database import session_factory
from app.models import Base
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, JSON, Text, Index
from sqlalchemy.dialects.mssql import NVARCHAR, TIMESTAMP

# ---------------------------------------------------------------------------
# 表名约定：os_sentiment_*
# ---------------------------------------------------------------------------

class SentimentTopic(Base):
    __tablename__ = 'os_sentiment_topic'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    name = Column(String(128), nullable=False)
    keywords = Column(JSON, default=list)
    exclude_keywords = Column(JSON, default=list)
    brand_entities = Column(JSON, default=list)
    product_line = Column(String(128), default='')
    status = Column(String(16), default='active')
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_sentiment_topic_plugin', 'plugin_id'),
    )


class SentimentSource(Base):
    __tablename__ = 'os_sentiment_source'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    topic_id = Column(NVARCHAR(36), nullable=False)
    source_type = Column(String(64), nullable=False)
    access_type = Column(String(32), default='api')
    endpoint = Column(Text, default='')
    credential_ref = Column(String(128), default='')
    interval_min = Column(Integer, default=60)
    rate_limit = Column(Integer, default=1000)
    status = Column(String(16), default='active')
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_sentiment_source_plugin', 'plugin_id'),
        Index('ix_sentiment_source_topic', 'topic_id'),
    )


class SentimentTask(Base):
    __tablename__ = 'os_sentiment_task'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    source_id = Column(NVARCHAR(36), nullable=False)
    trigger_type = Column(String(16), default='manual')
    started_at = Column(TIMESTAMP)
    finished_at = Column(TIMESTAMP)
    fetched = Column(Integer, default=0)
    inserted = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    error_msg = Column(Text, default='')

    __table_args__ = (
        Index('ix_sentiment_task_plugin', 'plugin_id'),
        Index('ix_sentiment_task_source', 'source_id'),
    )


class SentimentItem(Base):
    __tablename__ = 'os_sentiment_item'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    source_id = Column(NVARCHAR(36), nullable=False)
    topic_id = Column(NVARCHAR(36), nullable=False)
    external_id = Column(String(256), default='')
    title = Column(String(512), default='')
    content = Column(Text, default='')
    author = Column(String(256), default='')
    author_fans = Column(Integer, default=0)
    publish_at = Column(TIMESTAMP)
    url = Column(String(1024), default='')
    fingerprint = Column(String(128), default='')
    lang = Column(String(16), default='zh')
    raw = Column(JSON, default=dict)

    __table_args__ = (
        Index('ix_sentiment_item_plugin', 'plugin_id'),
        Index('ix_sentiment_item_topic_pub', 'topic_id', 'publish_at'),
        Index('ix_sentiment_item_fingerprint', 'fingerprint', unique=True),
        Index('ix_sentiment_item_url', 'url', postgresql_using='btree', postgresql_ops={'url': 'varchar_pattern_ops'}),
    )


class SentimentEmotion(Base):
    __tablename__ = 'os_sentiment_emotion'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    item_id = Column(NVARCHAR(36), nullable=False)
    polarity = Column(String(8), default='neutral')
    intensity = Column(Integer, default=3)
    model = Column(String(32), default='')
    rule_hit = Column(Boolean, default=False)
    confidence = Column(Integer, default=0)
    labeled_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_sentiment_emotion_plugin', 'plugin_id'),
        Index('ix_sentiment_emotion_item', 'item_id'),
    )


class SentimentEntity(Base):
    __tablename__ = 'os_sentiment_entity'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    item_id = Column(NVARCHAR(36), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_name = Column(String(256), nullable=False)
    normalized_name = Column(String(256), default='')
    confidence = Column(Integer, default=0)

    __table_args__ = (
        Index('ix_sentiment_entity_plugin', 'plugin_id'),
        Index('ix_sentiment_entity_item', 'item_id'),
    )


class SentimentEvent(Base):
    __tablename__ = 'os_sentiment_event'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    topic_id = Column(NVARCHAR(36), nullable=False)
    title = Column(String(512), default='')
    first_seen_at = Column(TIMESTAMP)
    peak_at = Column(TIMESTAMP)
    item_count = Column(Integer, default=0)
    spread_level = Column(String(16), default='low')
    status = Column(String(16), default='active')

    __table_args__ = (
        Index('ix_sentiment_event_plugin', 'plugin_id'),
        Index('ix_sentiment_event_topic', 'topic_id'),
    )


class SentimentEventItem(Base):
    __tablename__ = 'os_sentiment_event_item'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    event_id = Column(NVARCHAR(36), nullable=False)
    item_id = Column(NVARCHAR(36), nullable=False)
    relation_role = Column(String(32), default='republish')

    __table_args__ = (
        Index('ix_sentiment_event_item_plugin', 'plugin_id'),
        Index('ix_sentiment_event_item_event', 'event_id'),
        Index('ix_sentiment_event_item_item', 'item_id'),
    )


class SentimentAlertRule(Base):
    __tablename__ = 'os_sentiment_alert_rule'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    topic_id = Column(NVARCHAR(36), nullable=False)
    rule_type = Column(String(32), nullable=False)
    params = Column(JSON, default=dict)
    level = Column(String(8), default='S3')
    silence_window = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)

    __table_args__ = (
        Index('ix_sentiment_alert_rule_plugin', 'plugin_id'),
        Index('ix_sentiment_alert_rule_topic', 'topic_id'),
    )


class SentimentAlert(Base):
    __tablename__ = 'os_sentiment_alert'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    rule_id = Column(NVARCHAR(36), nullable=False)
    event_id = Column(NVARCHAR(36), nullable=False)
    level = Column(String(8), default='S3')
    status = Column(String(16), default='pending')
    owner_id = Column(String(36), default='')
    hit_detail = Column(JSON, default=dict)
    feedback = Column(String(16), default='')

    __table_args__ = (
        Index('ix_sentiment_alert_plugin', 'plugin_id'),
        Index('ix_sentiment_alert_rule', 'rule_id'),
        Index('ix_sentiment_alert_event', 'event_id'),
    )


class SentimentReport(Base):
    __tablename__ = 'os_sentiment_report'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    topic_id = Column(NVARCHAR(36), nullable=False)
    report_type = Column(String(16), default='daily')
    period_start = Column(TIMESTAMP)
    period_end = Column(TIMESTAMP)
    content = Column(Text, default='')
    ai_generated = Column(Boolean, default=False)
    confirmed_by = Column(String(36), default='')
    file_path = Column(String(512), default='')

    __table_args__ = (
        Index('ix_sentiment_report_plugin', 'plugin_id'),
        Index('ix_sentiment_report_topic', 'topic_id'),
    )


class SentimentKeywordStat(Base):
    __tablename__ = 'os_sentiment_keyword_stat'

    id = Column(NVARCHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String(64), nullable=False, default='sentiment')
    topic_id = Column(NVARCHAR(36), nullable=False)
    stat_date = Column(TIMESTAMP, nullable=False)
    keyword = Column(String(256), nullable=False)
    count = Column(Integer, default=0)
    delta_ratio = Column(Integer, default=0)

    __table_args__ = (
        Index('ix_sentiment_keyword_stat_plugin', 'plugin_id'),
        Index('ix_sentiment_keyword_stat_topic_date', 'topic_id', 'stat_date'),
    )


ALL_MODELS = [
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
]
