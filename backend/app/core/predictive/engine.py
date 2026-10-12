"""M9 预测引擎：流失 / 转化概率预测（可插拔 + 规则兜底）。

设计要点：
- Provider 可插拔：``register_provider()`` 注册本地 / 云端模型 provider，
  后续模型路由（M6/M7）接入时只需实现 ``PredictionProvider`` 接口并注册；
- 规则兜底：内置 ``RuleProvider`` 基于业务经验规则对每个主体打分，输出
  概率 + 置信度 + 可解释理由，在无本地模型 / 模型路由不可用时兜底；
- 路由策略：``mode=rule`` 直接使用规则；``mode=local/api`` 优先查 provider
  注册表，未注册或调用失败且 ``rule_fallback=True`` 时降级为规则打分，
  否则抛出 ``PredictiveEngineError``；
- 输出约束：概率与置信度均落在 [0, 1]，概率档位 high/medium/low 供
  人群包引擎（M10）圈选复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from app.models.predictive import (
    PREDICTION_BANDS,
    PREDICTION_MODES,
    PREDICTION_TARGETS,
)


class PredictiveEngineError(RuntimeError):
    """预测引擎异常：目标非法 / 模式非法 / 全链不可用且不允许兜底。"""


# ---------------------------------------------------------------- 输出结构
@dataclass
class SubjectPrediction:
    """单个主体的预测输出。"""

    subject_key: str
    subject_name: Optional[str] = None
    probability: float = 0.5
    band: str = "medium"
    mode: str = "rule"
    model: str = ""
    confidence: Optional[float] = None
    features: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class PredictionOutcome:
    """一次预测任务的引擎输出（含实际路由信息）。"""

    predictions: list[SubjectPrediction]
    mode_used: str
    model_used: str
    rule_fallback: bool = False


class PredictionProvider(Protocol):
    """可插拔预测 provider 接口：实现后可注册进引擎。"""

    name: str

    def predict(
        self,
        *,
        tenant_id: int,
        target: str,
        subjects: list[dict[str, Any]],
        features: Optional[dict[str, Any]],
        threshold: float,
    ) -> list[SubjectPrediction]:
        ...


# ---------------------------------------------------------------- 规则兜底
# 流失规则：特征值越高代表流失风险越高（或越低），权重合计 1.0
_CHURN_RULES: list[tuple[str, float, bool]] = [
    ("last_active_days", 0.25, True),   # 距上次活跃越久，流失风险越高
    ("login_count", 0.20, False),       # 登录越少，流失风险越高
    ("order_count", 0.20, False),       # 下单越少，流失风险越高
    ("spend_amount", 0.15, False),      # 消费金额越低，流失风险越高
    ("complaint_count", 0.10, True),    # 投诉越多，流失风险越高
    ("support_tickets", 0.10, True),    # 工单越多，流失风险越高
]

# 转化规则：特征值越高代表转化概率越高（或越低）
_CONVERSION_RULES: list[tuple[str, float, bool]] = [
    ("visit_count", 0.25, True),          # 访问越多，转化概率越高
    ("cart_count", 0.20, True),           # 加购越多，转化概率越高
    ("content_views", 0.15, True),        # 内容消费越多，转化概率越高
    ("recent_purchase_days", 0.15, False),  # 距上次购买越近，转化概率越高
    ("coupon_used", 0.15, True),          # 使用优惠券倾向转化
    ("click_rate", 0.10, True),           # 点击率越高，转化概率越高
]

_BAND_HIGH = 0.7
_BAND_MEDIUM = 0.4


def _as_float(value: Any) -> Optional[float]:
    """宽松数值化：None / 不可转数值返回 None，布尔视为 0/1。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_band(probability: float) -> str:
    if probability >= _BAND_HIGH:
        return "high"
    if probability >= _BAND_MEDIUM:
        return "medium"
    return "low"


class RuleProvider:
    """规则兜底模型：经验规则线性加权 + 置信度按特征覆盖度估计。"""

    name = "rule"

    def __init__(self) -> None:
        self._rules: dict[str, list[tuple[str, float, bool]]] = {
            "churn": _CHURN_RULES,
            "conversion": _CONVERSION_RULES,
        }

    def predict(
        self,
        *,
        tenant_id: int,
        target: str,
        subjects: list[dict[str, Any]],
        features: Optional[dict[str, Any]],
        threshold: float,
    ) -> list[SubjectPrediction]:
        rules = self._rules[target]
        expected = len(rules)
        out: list[SubjectPrediction] = []
        for subject in subjects:
            key = subject.get("key") or f"subject_{len(out) + 1}"
            name = subject.get("name")
            feats = subject.get("features") or {}
            if not feats and features:
                feats = features.get(key) or features

            score = 0.5
            used = 0
            reasons: list[str] = []
            for feat, weight, higher_is_risk in rules:
                raw = _as_float(feats.get(feat))
                if raw is None:
                    continue
                used += 1
                if higher_is_risk:
                    # 值越高，风险/转化越高：0 对应 0.5 基准，向 1 方向偏移
                    contribution = (0.5 + min(raw, 2.0) * 0.25) * weight
                else:
                    # 值越高，风险/转化越低：反向偏移
                    contribution = (0.5 - min(raw, 2.0) * 0.25) * weight
                score += contribution - 0.5 * weight
                reasons.append(f"{feat}={raw}")
            if used == 0:
                score = 0.5
            probability = max(0.05, min(0.95, score))
            confidence = 0.4 + 0.55 * (used / expected) if expected else 0.95
            out.append(
                SubjectPrediction(
                    subject_key=str(key),
                    subject_name=name,
                    probability=round(probability, 5),
                    band=_to_band(probability),
                    mode="rule",
                    model="rule",
                    confidence=round(confidence, 4),
                    features={k: v for k, v in feats.items()},
                    reasons=reasons,
                )
            )
        return out


# ---------------------------------------------------------------- 引擎路由
_PROVIDERS: dict[str, PredictionProvider] = {}


def register_provider(provider: PredictionProvider) -> None:
    """注册可插拔 provider（本地 / 云端模型），供引擎路由使用。"""
    if not getattr(provider, "name", None):
        raise PredictiveEngineError("provider 必须声明 name")
    _PROVIDERS[provider.name] = provider


def get_provider(name: str) -> Optional[PredictionProvider]:
    return _PROVIDERS.get(name)


def _validate_target(target: str) -> None:
    if target not in PREDICTION_TARGETS:
        raise PredictiveEngineError(f"不支持的预测目标: {target}（可选 {PREDICTION_TARGETS}）")


def _validate_mode(mode: str) -> None:
    if mode not in PREDICTION_MODES:
        raise PredictiveEngineError(f"不支持的模型路由模式: {mode}（可选 {PREDICTION_MODES}）")


def run_prediction(
    *,
    tenant_id: int,
    target: str,
    subjects: list[dict[str, Any]],
    features: Optional[dict[str, Any]] = None,
    mode: str = "local",
    threshold: float = 0.5,
    rule_fallback: bool = True,
) -> PredictionOutcome:
    """执行一次预测。

    - 校验 target / mode / subjects；
    - 按 mode 路由 provider；local/api 未注册或调用失败时按 rule_fallback
      降级为规则打分，否则抛错；
    - 返回 PredictionOutcome（含实际使用的 mode / model / 是否兜底）。
    """
    _validate_target(target)
    _validate_mode(mode)
    if not subjects:
        raise PredictiveEngineError("预测主体列表为空")

    provider = _PROVIDERS.get(mode)
    fallback = False
    mode_used = mode
    model_used = getattr(provider, "name", "") if provider else ""

    if provider is None:
        if mode == "rule":
            provider = _PROVIDERS["rule"]
            model_used = "rule"
        elif rule_fallback:
            fallback = True
            provider = _PROVIDERS["rule"]
            mode_used = "rule"
            model_used = "rule"
        else:
            raise PredictiveEngineError(
                f"模型路由模式 {mode} 不可用，且 rule_fallback=False 禁止规则兜底"
            )

    try:
        predictions = provider.predict(
            tenant_id=tenant_id,
            target=target,
            subjects=subjects,
            features=features,
            threshold=threshold,
        )
    except PredictiveEngineError:
        raise
    except Exception as exc:  # pragma: no cover - provider 内部故障
        if mode == "rule" or not rule_fallback:
            raise PredictiveEngineError(f"预测 provider 执行失败: {exc}") from exc
        fallback = True
        provider = _PROVIDERS["rule"]
        mode_used = "rule"
        model_used = "rule"
        predictions = provider.predict(
            tenant_id=tenant_id,
            target=target,
            subjects=subjects,
            features=features,
            threshold=threshold,
        )

    return PredictionOutcome(
        predictions=predictions,
        mode_used=mode_used,
        model_used=model_used,
        rule_fallback=fallback,
    )


# 引擎内置规则兜底 provider
register_provider(RuleProvider())
