"""AI 能力接口：数据分级 / 分析洞察 / 权限处置 / 审计。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.models.ai import (
    DATA_LEVEL_META,
    GRADE_OBJECT_TYPES,
    AiActionItem,
    AiActionPolicy,
    AiDataLevelRule,
    AiInsight,
)
from app.models.base import get_db
from app.models.datasource import DataSource
from app.models.import_task import ImportTask
from app.models.metric import Metric
from app.schemas.ai import (
    ActionDecisionIn,
    ActionDecisionLevelIn,
    ActionOut,
    ActionRevokeIn,
    AiConfigOut,
    AnalysisOut,
    AnalysisRunIn,
    AuditOut,
    DecisionBoardOut,
    DecisionTraceOut,
    GradeRunIn,
    GradeRunOut,
    InsightOut,
    LevelRecordOut,
    LevelRuleCreate,
    LevelRuleOut,
    LevelRuleUpdate,
    PolicyDecideOut,
    PolicyOut,
    PolicyUpdate,
)
from app.schemas.common import ApiResponse, PageResult
from app.services.ai import analyzer, governor, grader
from app.services.ai.llm_client import LLMClient

router = APIRouter()


# ================================================= 配置与健康
@router.get("/config", response_model=ApiResponse[AiConfigOut], summary="AI 配置与状态")
def ai_config(
    probe: bool = Query(False, description="是否实际探测模型可用性"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[AiConfigOut]:
    """展示 AI 双模式（api 云端 / local 本地）配置、当前模式与实际可用性。"""
    info = analyzer.ai_mode_info()
    probe_result = None
    if probe:
        probe_result = LLMClient().readiness()
    data = AiConfigOut(
        **info,
        probe=probe_result,
        level_meta=DATA_LEVEL_META,
        statistics=governor.statistics(db, tenant_id),
    )
    return ApiResponse[AiConfigOut](data=data)


@router.get("/statistics", response_model=ApiResponse[dict], summary="AI 治理概览")
def ai_statistics(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """洞察 / 处置单 / AI 自动处置与人工待办的数量统计。"""
    return ApiResponse[dict](data=governor.statistics(db, tenant_id))


# ================================================= 数据分级：规则
@router.post("/level/rules/seed", response_model=ApiResponse[dict], summary="写入内置分级规则")
def seed_level_rules(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """幂等写入系统内置分级规则（已存在则跳过）。"""
    added = grader.ensure_default_rules(db, tenant_id)
    return ApiResponse[dict](data={"added": added, "total": len(grader.list_rules(db, tenant_id))})


@router.get("/level/rules", response_model=ApiResponse[list[LevelRuleOut]], summary="分级规则列表")
def list_level_rules(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[LevelRuleOut]]:
    rows = grader.list_rules(db, tenant_id)
    return ApiResponse[list[LevelRuleOut]](data=[LevelRuleOut.model_validate(r) for r in rows])


@router.post("/level/rules", response_model=ApiResponse[LevelRuleOut], summary="新建分级规则")
def create_level_rule(
    payload: LevelRuleCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[LevelRuleOut]:
    exists = db.execute(
        select(AiDataLevelRule).where(
            AiDataLevelRule.tenant_id == tenant_id, AiDataLevelRule.code == payload.code
        )
    ).scalars().first()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"规则编码已存在: {payload.code}")
    rule = AiDataLevelRule(tenant_id=tenant_id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ApiResponse[LevelRuleOut](data=LevelRuleOut.model_validate(rule))


@router.put("/level/rules/{rule_id}", response_model=ApiResponse[LevelRuleOut], summary="更新分级规则")
def update_level_rule(
    rule_id: int,
    payload: LevelRuleUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[LevelRuleOut]:
    rule = db.execute(
        select(AiDataLevelRule).where(
            AiDataLevelRule.tenant_id == tenant_id, AiDataLevelRule.id == rule_id
        )
    ).scalars().first()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"规则不存在: {rule_id}")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return ApiResponse[LevelRuleOut](data=LevelRuleOut.model_validate(rule))


@router.delete("/level/rules/{rule_id}", response_model=ApiResponse[dict], summary="删除分级规则")
def delete_level_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    rule = db.execute(
        select(AiDataLevelRule).where(
            AiDataLevelRule.tenant_id == tenant_id, AiDataLevelRule.id == rule_id
        )
    ).scalars().first()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"规则不存在: {rule_id}")
    db.delete(rule)
    db.commit()
    return ApiResponse[dict](data={"id": rule_id, "deleted": True})


# ================================================= 数据分级：执行与查询
def _collect_objects(db: Session, tenant_id: int, object_type: str, limit: int) -> list:
    if object_type == "metric":
        return list(
            db.execute(select(Metric).where(Metric.tenant_id == tenant_id).limit(limit)).scalars().all()
        )
    if object_type == "data_source":
        return list(
            db.execute(
                select(DataSource).where(DataSource.tenant_id == tenant_id).limit(limit)
            ).scalars().all()
        )
    if object_type == "import_task":
        return list(
            db.execute(
                select(ImportTask)
                .where(ImportTask.tenant_id == tenant_id)
                .order_by(ImportTask.id.desc())
                .limit(limit)
            ).scalars().all()
        )
    return []


@router.post("/level/grade", response_model=ApiResponse[GradeRunOut], summary="触发数据分级")
def run_grade(
    payload: GradeRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[GradeRunOut]:
    """规则引擎批量定级；use_ai=true 时额外调用大模型给出定级建议。"""
    rule_result = grader.grade_all(db, tenant_id, payload.object_types)
    ai_result = None
    if payload.use_ai:
        ai_items: list[dict] = []
        mode = model = None
        for object_type in payload.object_types:
            objects = _collect_objects(db, tenant_id, object_type, payload.ai_limit)
            if not objects:
                continue
            result = grader.ai_suggest_levels(db, tenant_id, object_type, objects, limit=payload.ai_limit)
            mode, model = result.get("mode"), result.get("model")
            for item in result.get("items", []):
                item["object_type"] = object_type
                ai_items.append(item)
        ai_result = {"mode": mode, "model": model, "items": ai_items, "applied": len(ai_items)}
        governor.audit(
            db,
            tenant_id,
            actor_type="ai",
            actor=model or "ai",
            action="grade",
            object_type="ai_data_level",
            detail=f"AI 辅助定级 {len(ai_items)} 项对象（模式 {mode}）",
        )
    return ApiResponse[GradeRunOut](data=GradeRunOut(rule_engine=rule_result, ai=ai_result))


@router.get("/level/records", response_model=ApiResponse[list[LevelRecordOut]], summary="分级结果列表")
def list_level_records(
    object_type: Optional[str] = Query(None, description="metric/data_source/import_task"),
    level: Optional[str] = Query(None, description="L1-L4"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[LevelRecordOut]]:
    rows = grader.list_records(db, tenant_id, object_type=object_type, level=level)
    return ApiResponse[list[LevelRecordOut]](data=[LevelRecordOut.model_validate(r) for r in rows])


@router.get("/level/object", response_model=ApiResponse[dict], summary="单对象实时定级")
def grade_single_object(
    object_type: str = Query(..., description=f"对象类型：{'/'.join(GRADE_OBJECT_TYPES)}"),
    object_id: int = Query(..., description="对象 ID"),
    persist: bool = Query(False, description="是否把结果写入分级记录"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """按规则实时判定单个对象的级别，并返回命中的规则与依据。"""
    obj = None
    if object_type == "metric":
        obj = db.execute(
            select(Metric).where(Metric.tenant_id == tenant_id, Metric.id == object_id)
        ).scalars().first()
    elif object_type == "data_source":
        obj = db.execute(
            select(DataSource).where(DataSource.tenant_id == tenant_id, DataSource.id == object_id)
        ).scalars().first()
    elif object_type == "import_task":
        obj = db.execute(
            select(ImportTask).where(ImportTask.tenant_id == tenant_id, ImportTask.id == object_id)
        ).scalars().first()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"对象不存在: {object_type}#{object_id}"
        )

    ctx = grader.build_context(obj)
    level, rule, reason = grader.resolve_level(db, tenant_id, object_type, ctx)
    record = None
    if persist:
        record = grader.grade_object(db, tenant_id, object_type, obj, source="rule")
    return ApiResponse[dict](
        data={
            "object_type": object_type,
            "object_id": object_id,
            "object_code": ctx.get("code") or ctx.get("name"),
            "level": level,
            "level_meta": DATA_LEVEL_META.get(level),
            "rule_code": rule.code if rule else None,
            "rule_name": rule.name if rule else None,
            "reason": reason,
            "context": {k: v for k, v in ctx.items() if k != "text"},
            "persisted": bool(record),
        }
    )


# ================================================= AI 分析
@router.post("/analyze", response_model=ApiResponse[dict], summary="发起 AI 分析")
def run_analysis(
    payload: AnalysisRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """采集数据快照 → 调用模型（api/local）→ 产出洞察建议 → 按权限自动路由处置单。"""
    analysis = analyzer.run_analysis(
        db,
        tenant_id,
        scope=payload.scope,
        granularity=payload.granularity,
        dim_key=payload.dim_key,
        codes=payload.codes,
        title=payload.title or "",
        mode=payload.mode,
        model=payload.model,
        max_insights=payload.max_insights,
    )
    insights = analyzer.analysis_insights(db, tenant_id, analysis.id)
    routed = None
    if analysis.status == "success" and payload.auto_route:
        routed = governor.route_analysis(db, tenant_id, analysis.id)
        insights = analyzer.analysis_insights(db, tenant_id, analysis.id)

    governor.audit(
        db,
        tenant_id,
        actor_type="ai",
        actor=analysis.model or "ai",
        action="analyze",
        object_type="analysis",
        object_id=analysis.id,
        from_state="running",
        to_state=analysis.status,
        detail=f"范围 {analysis.scope}，模式 {analysis.mode}，产出洞察 {analysis.insight_count} 条",
    )
    return ApiResponse[dict](
        data={
            "analysis": AnalysisOut.model_validate(analysis),
            "insights": [InsightOut.model_validate(i) for i in insights],
            "routing": routed,
        }
    )


@router.get("/analyses", response_model=ApiResponse[list[AnalysisOut]], summary="分析历史")
def list_analyses(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[AnalysisOut]]:
    rows = analyzer.list_analyses(db, tenant_id, limit=limit)
    return ApiResponse[list[AnalysisOut]](data=[AnalysisOut.model_validate(r) for r in rows])


@router.get("/analyses/{analysis_id}", response_model=ApiResponse[dict], summary="分析详情")
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    analysis = analyzer.get_analysis(db, tenant_id, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"分析不存在: {analysis_id}")
    insights = analyzer.analysis_insights(db, tenant_id, analysis_id)
    actions = governor.list_actions(db, tenant_id, analysis_id=analysis_id, limit=200)
    return ApiResponse[dict](
        data={
            "analysis": AnalysisOut.model_validate(analysis),
            "insights": [InsightOut.model_validate(i) for i in insights],
            "actions": [ActionOut.model_validate(a) for a in actions],
        }
    )


@router.get("/analyses/{analysis_id}/insights", response_model=ApiResponse[list[InsightOut]], summary="分析洞察")
def list_analysis_insights(
    analysis_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[InsightOut]]:
    rows = analyzer.analysis_insights(db, tenant_id, analysis_id)
    return ApiResponse[list[InsightOut]](data=[InsightOut.model_validate(r) for r in rows])


@router.get("/insights", response_model=ApiResponse[PageResult[InsightOut]], summary="洞察列表")
def list_insights(
    insight_status: Optional[str] = Query(None, alias="status", description="new/routed/resolved/dismissed"),
    severity: Optional[str] = Query(None, description="info/warning/critical"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[InsightOut]]:
    from sqlalchemy import func
    base_stmt = select(AiInsight).where(AiInsight.tenant_id == tenant_id)
    if insight_status:
        base_stmt = base_stmt.where(AiInsight.status == insight_status)
    if severity:
        base_stmt = base_stmt.where(AiInsight.severity == severity)
    total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar() or 0
    rows = analyzer.list_insights(db, tenant_id, status=insight_status, severity=severity, limit=limit, offset=offset)
    return ApiResponse[PageResult[InsightOut]](data=PageResult(total=total, page=(offset // limit) + 1, page_size=limit, items=[InsightOut.model_validate(r) for r in rows]))


@router.post("/insights/route", response_model=ApiResponse[dict], summary="批量路由洞察")
def route_insights(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """把所有未路由洞察按权限矩阵生成处置单（权限内 AI 自动执行，其余转人工）。"""
    result = governor.route_pending(db, tenant_id)
    return ApiResponse[dict](data=result)


# ================================================= 权限策略
@router.post("/policies/seed", response_model=ApiResponse[dict], summary="写入内置权限策略")
def seed_policies(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    added = governor.ensure_default_policies(db, tenant_id)
    return ApiResponse[dict](data={"added": added, "total": len(governor.list_policies(db, tenant_id))})


@router.get("/policies", response_model=ApiResponse[list[PolicyOut]], summary="权限策略列表")
def list_policies(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[PolicyOut]]:
    rows = governor.list_policies(db, tenant_id)
    return ApiResponse[list[PolicyOut]](data=[PolicyOut.model_validate(r) for r in rows])


@router.put("/policies/{policy_id}", response_model=ApiResponse[PolicyOut], summary="更新权限策略")
def update_policy(
    policy_id: int,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PolicyOut]:
    """调整策略的放行/复核/审批开关（配置变更，仅影响后续判定）。"""
    policy = db.execute(
        select(AiActionPolicy).where(
            AiActionPolicy.tenant_id == tenant_id, AiActionPolicy.id == policy_id
        )
    ).scalars().first()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"策略不存在: {policy_id}")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    governor.audit(
        db,
        tenant_id,
        actor_type="human",
        actor="admin",
        action="update_policy",
        object_type="action_policy",
        object_id=policy.id,
        detail=f"策略 {policy.code} 已更新",
    )
    return ApiResponse[PolicyOut](data=PolicyOut.model_validate(policy))


@router.get("/policies/decide", response_model=ApiResponse[PolicyDecideOut], summary="权限判定试算")
def decide_policy(
    data_level: str = Query(..., description="L1-L4"),
    actor: str = Query("ai", description="ai / human"),
    action_type: str = Query("notify", description="动作类型"),
    severity: str = Query("info", description="info/warning/critical"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PolicyDecideOut]:
    """给定「数据级别 × 执行者 × 动作 × 严重度」试算是否放行、是否需复核/审批。"""
    decision = governor.decide(
        db, tenant_id, level=data_level, actor=actor, action_type=action_type, severity=severity
    )
    policy: Optional[AiActionPolicy] = decision.get("policy")
    return ApiResponse[PolicyDecideOut](
        data=PolicyDecideOut(
            data_level=data_level,
            actor=actor,
            action_type=action_type,
            severity=severity,
            allow=bool(decision["allow"]),
            require_review=bool(decision["require_review"]),
            require_approval=bool(decision["require_approval"]),
            policy_code=policy.code if policy else None,
            policy_name=policy.name if policy else None,
            reason=str(decision["reason"]),
        )
    )


# ================================================= 处置单
@router.get("/actions", response_model=ApiResponse[PageResult[ActionOut]], summary="处置单列表")
def list_actions(
    action_status: Optional[str] = Query(
        None, alias="status", description="pending/auto_executed/approved/rejected/executed/failed"
    ),
    handler: Optional[str] = Query(None, description="ai / human"),
    data_level: Optional[str] = Query(None, description="L1-L4"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[ActionOut]]:
    from sqlalchemy import func

    base_stmt = select(AiActionItem).where(AiActionItem.tenant_id == tenant_id)
    if action_status:
        base_stmt = base_stmt.where(AiActionItem.status == action_status)
    if handler:
        base_stmt = base_stmt.where(AiActionItem.handler == handler)
    if data_level:
        base_stmt = base_stmt.where(AiActionItem.data_level == data_level)
    total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar() or 0
    rows = governor.list_actions(
        db, tenant_id, status=action_status, handler=handler, level=data_level, limit=limit, offset=offset
    )
    return ApiResponse[PageResult[ActionOut]](data=PageResult(total=total, page=(offset // limit) + 1, page_size=limit, items=[ActionOut.model_validate(r) for r in rows]))


@router.post("/actions/{action_id}/approve", response_model=ApiResponse[ActionOut], summary="人工审批通过")
def approve_action(
    action_id: int,
    payload: ActionDecisionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ActionOut]:
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    if item.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"仅待办状态可审批，当前状态: {item.status}"
        )
    item = governor.approve_action(db, tenant_id, item, payload.operator, payload.note or "")
    return ApiResponse[ActionOut](data=ActionOut.model_validate(item))


@router.post("/actions/{action_id}/reject", response_model=ApiResponse[ActionOut], summary="人工驳回")
def reject_action(
    action_id: int,
    payload: ActionDecisionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ActionOut]:
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    if item.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"仅待办状态可驳回，当前状态: {item.status}"
        )
    item = governor.reject_action(db, tenant_id, item, payload.operator, payload.note or "")
    return ApiResponse[ActionOut](data=ActionOut.model_validate(item))


@router.post("/actions/{action_id}/execute", response_model=ApiResponse[ActionOut], summary="人工执行处置")
def execute_action(
    action_id: int,
    payload: ActionDecisionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ActionOut]:
    """登记式执行：记录处置结论与结果并留痕，不对生产数据做破坏性变更。

    需审批的处置单必须先 approve 再 execute。
    """
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    if item.status in ("rejected", "executed", "auto_executed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"当前状态不可执行: {item.status}"
        )
    if item.status == "pending" and item.review_required:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="该处置单需人工审批后方可执行（先调用 approve）"
        )
    item = governor.execute_action(
        db, tenant_id, item, payload.operator, payload.note or "", payload.result or ""
    )
    return ApiResponse[ActionOut](data=ActionOut.model_validate(item))


# ================================================= 决策分级授权与叫停
@router.get("/decisions/board", response_model=ApiResponse[DecisionBoardOut], summary="决策分级授权看板")
def decision_board(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[DecisionBoardOut]:
    """三级决策授权概览：各级数量、待办、已叫停、自主执行与演练模式计数。"""
    data = governor.decision_board(db, tenant_id)
    return ApiResponse[DecisionBoardOut](data=DecisionBoardOut.model_validate(data))


@router.put("/actions/{action_id}/decision-level", response_model=ApiResponse[ActionOut], summary="调整决策分级")
def set_action_decision_level(
    action_id: int,
    payload: ActionDecisionLevelIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ActionOut]:
    """把处置单在 仅用户决策 / 需用户授权 / 智能体自主 三级之间调整，来源记为 manual。"""
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    try:
        item = governor.update_decision_level(
            db, tenant_id, item, payload.decision_level, payload.operator, payload.note or ""
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ApiResponse[ActionOut](data=ActionOut.model_validate(item))


@router.post("/actions/{action_id}/revoke", response_model=ApiResponse[ActionOut], summary="一键叫停/撤销")
def revoke_action(
    action_id: int,
    payload: ActionRevokeIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ActionOut]:
    """用户一键叫停 AI 决策：立即失效、停止引用并全过程留痕。"""
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    try:
        item = governor.revoke_action(db, tenant_id, item, payload.operator, payload.reason or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ApiResponse[ActionOut](data=ActionOut.model_validate(item))


@router.post("/actions/{action_id}/restore", response_model=ApiResponse[ActionOut], summary="还原叫停决策")
def restore_action(
    action_id: int,
    payload: ActionDecisionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ActionOut]:
    """还原被误叫停的决策，回到撤销前状态。"""
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    try:
        item = governor.restore_action(db, tenant_id, item, payload.operator, payload.note or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ApiResponse[ActionOut](data=ActionOut.model_validate(item))


@router.get("/actions/{action_id}/trace", response_model=ApiResponse[DecisionTraceOut], summary="决策全过程追溯")
def action_trace(
    action_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[DecisionTraceOut]:
    """单条处置单全链路留痕：洞察生成 → 分级路由 → 审批/执行 → 撤销/还原。"""
    item = governor.get_action(db, tenant_id, action_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"处置单不存在: {action_id}")
    entries = governor.decision_trace(db, tenant_id, item)
    return ApiResponse[DecisionTraceOut](
        data=DecisionTraceOut(action=ActionOut.model_validate(item), trace=entries)
    )


# ================================================= 审计
@router.get("/audit", response_model=ApiResponse[list[AuditOut]], summary="审计日志")
def list_audit(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[AuditOut]]:
    rows = governor.list_audit(db, tenant_id, limit=limit)
    return ApiResponse[list[AuditOut]](data=[AuditOut.model_validate(r) for r in rows])
