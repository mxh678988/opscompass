"""ORM 模型统一导出，便于 Alembic 自动发现。"""

from app.models.ai import (  # noqa: F401
    AiActionItem,
    AiActionPolicy,
    AiAnalysis,
    AiAuditLog,
    AiDataLevelRecord,
    AiDataLevelRule,
    AiInsight,
)
from app.models.auth import (  # noqa: F401
    AuditLog,
    Permission,
    Role,
    User,
    role_permission,
    user_role,
)
from app.models.base import Base  # noqa: F401
from app.models.collect import CollectRun, CollectTask  # noqa: F401
from app.models.datasource import DataSource  # noqa: F401
from app.models.import_task import ImportTask  # noqa: F401
from app.models.metric import (  # noqa: F401
    Metric,
    MetricCategory,
    MetricDimension,
    MetricValue,
    metric_dimension_rel,
)
from app.models.model_hub import (  # noqa: F401
    ENDPOINT_KINDS,
    VRAM_TIERS,
    AIModelEndpoint,
)
from app.models.learning import (  # noqa: F401
    CASE_STATUSES,
    DECISION_RESULTS,
    EXPERIMENT_STATUSES,
    EXPERIMENT_WINNERS,
    OUTCOME_RESULTS,
    LearnCase,
    LearnExperiment,
    LearnFeedback,
    LearnPolicyWeight,
)
from app.models.ops_compass import (
    Website,
    WebsitePage,
    ProductItem,
    SeoTask,
    PageSeoTask,
    GeoTask,
    WebsiteAiConfig,
    MediaItem,
    PageMediaRef,
)
from app.models.marketing import (  # noqa: F401
    ChannelCampaign,
    ChannelEvent,
    MarketingChannel,
)
from app.models.tenant import Tenant  # noqa: F401
from app.models.storage import (  # noqa: F401
    DATA_KINDS,
    MATCH_FIELDS,
    ConsistencyCheck,
    DocIndex,
    StorageRouteRule,
    TsMetricPoint,
)

__all__ = [
    "Base",
    "Tenant",
    "DataSource",
    "ImportTask",
    "MetricCategory",
    "Metric",
    "MetricDimension",
    "MetricValue",
    "metric_dimension_rel",
    "StorageRouteRule",
    "DocIndex",
    "TsMetricPoint",
    "ConsistencyCheck",
    "DATA_KINDS",
    "MATCH_FIELDS",
    "AiDataLevelRule",
    "AiDataLevelRecord",
    "AiAnalysis",
    "AiInsight",
    "AiActionPolicy",
    "AiActionItem",
    "AiAuditLog",
    "User",
    "Role",
    "Permission",
    "user_role",
    "role_permission",
    "AuditLog",
    "Website",
    "WebsitePage",
    "ProductItem",
    "SeoTask",
    "PageSeoTask",
    "GeoTask",
    "WebsiteAiConfig",
    "MediaItem",
    "PageMediaRef",
    "MarketingChannel",
    "ChannelCampaign",
    "ChannelEvent",
    "CollectTask",
    "CollectRun",
    "AIModelEndpoint",
    "ENDPOINT_KINDS",
    "VRAM_TIERS",
    "LearnFeedback",
    "LearnPolicyWeight",
    "LearnCase",
    "LearnExperiment",
    "DECISION_RESULTS",
    "OUTCOME_RESULTS",
    "CASE_STATUSES",
    "EXPERIMENT_STATUSES",
    "EXPERIMENT_WINNERS",
]
