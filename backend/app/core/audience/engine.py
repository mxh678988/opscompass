"""M10 人群包引擎：基于预测概率区间圈选人群。

职责：
- 概率区间校验（[0,1]、下限 <= 上限）与归一化；
- 从 M9 预测结果（oc_prediction_result）或既有人群包成员（oc_audience_member）
  中按 [min_prob, max_prob] 闭区间与概率档位筛选候选主体；
- 供服务层（audience_service）生成人群包、复用与落库。

设计要点：
- 区间为闭区间：min_prob 与 max_prob 均含端点（如 0.6-0.9 包含 0.60 与 0.90）；
- 至少需要给出一个筛选条件（min_prob / max_prob / band / source 引用之一），
  禁止无约束全量圈选，避免误建空泛人群包；
- 圈选候选概率精度按模型 Numeric(6,5) 对齐，比较前做五位小数归一。
"""

from __future__ import annotations

from typing import Any, Optional

from app.models.audience import SEGMENT_TARGETS
from app.models.predictive import PREDICTION_TARGETS


class AudienceEngineError(RuntimeError):
    """人群包引擎业务异常（参数 / 状态非法）。"""


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_range(
    min_prob: Optional[float], max_prob: Optional[float]
) -> tuple[Optional[float], Optional[float]]:
    """归一化并校验概率区间，返回 (lo, hi) 闭区间端点。

    - 端点空值允许（表示开放区间）；
    - 端点在 [0,1] 内，且 lo <= hi（当两者均给定时）。
    """
    lo = None if min_prob is None else round(_f(min_prob), 5)
    hi = None if max_prob is None else round(_f(max_prob), 5)
    if lo is not None and not (0.0 <= lo <= 1.0):
        raise AudienceEngineError(f"概率下限非法: {lo}（需在 [0,1] 内）")
    if hi is not None and not (0.0 <= hi <= 1.0):
        raise AudienceEngineError(f"概率上限非法: {hi}（需在 [0,1] 内）")
    if lo is not None and hi is not None and lo > hi:
        raise AudienceEngineError(f"概率区间非法: 下限 {lo} 大于上限 {hi}")
    return lo, hi


def validate_target(target: str) -> None:
    if target not in PREDICTION_TARGETS:
        raise AudienceEngineError(
            f"不支持的圈选目标: {target}（可选 {' / '.join(SEGMENT_TARGETS)}）"
        )


def validate_band(band: Optional[str]) -> None:
    if band is not None and band not in ("high", "medium", "low"):
        raise AudienceEngineError(f"不支持的概率档位: {band}（可选 high/medium/low）")


def validate_filters(
    *,
    source_job_id: Optional[int] = None,
    source_segment_id: Optional[int] = None,
    min_prob: Optional[float] = None,
    max_prob: Optional[float] = None,
    band: Optional[str] = None,
) -> None:
    """至少提供一个圈选条件，避免无约束全量圈选。"""
    if (
        source_job_id is None
        and source_segment_id is None
        and min_prob is None
        and max_prob is None
        and band is None
    ):
        raise AudienceEngineError("至少需要提供一个圈选条件（概率区间 / 档位 / 来源）")


def in_probability_range(
    probability: Any, lo: Optional[float], hi: Optional[float]
) -> bool:
    """闭区间命中判断：lo <= p <= hi（空端点表示开放）。"""
    p = round(_f(probability), 5)
    if lo is not None and p < lo:
        return False
    if hi is not None and p > hi:
        return False
    return True


def matches_band(band_value: Any, band: Optional[str]) -> bool:
    if band is None:
        return True
    return str(band_value or "") == band
