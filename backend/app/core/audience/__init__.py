"""M10 人群包引擎：基于预测概率区间圈选人群。"""

from app.core.audience.engine import (  # noqa: F401
    AudienceEngineError,
    in_probability_range,
    matches_band,
    normalize_range,
    validate_band,
    validate_filters,
    validate_target,
)

__all__ = [
    "AudienceEngineError",
    "normalize_range",
    "validate_target",
    "validate_band",
    "validate_filters",
    "in_probability_range",
    "matches_band",
]
