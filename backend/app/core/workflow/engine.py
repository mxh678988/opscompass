"""OS 内核 · 工作流引擎（M5）。

职责（对应设计文档 3.2 工作流引擎）：
- 流程定义由 ``app/core/workflow/dsl.py`` 校验，本模块只负责运行态；
- 状态机驱动：实例 ``oc_core_workflow_instance`` + 步骤
  ``oc_core_workflow_step`` 全部落库，中断后可续跑；
- 幂等：步骤唯一键 ``instance_id + seq``（数据库唯一约束 + 引擎检查），
  重复推进不会产生重复副作用；
- 人工节点：``wait`` 步骤置 waiting 生成待办，可确认或超时兜底
  （``confirm`` / ``timeout_next`` / ``timeout_minutes``）；
- 失败补偿：task 可配 ``compensate`` handler，失败先补偿再置 failed，
  无补偿则标记人工介入；
- 每步可挂 SLA（M4）：步骤配置含 ``sla`` 时由调用方注入的 ``sla_creator``
  创建任务计时（PluginRuntime 装配时以 ``create_sla`` 包一层）。

对外主入口：
``create_instance`` 建实例并物化步骤序列；``run`` 推进到人工/完成/失败；
``confirm_wait_step`` / ``timeout_wait_step`` 处理人工节点；
``scan_waiting_timeouts`` 供调度侧批量扫描超时待办。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.workflow.dsl import validate_definition
from app.models.workflow import (
    CoreWorkflowInstance,
    CoreWorkflowStep,
    WORKFLOW_STEP_STATUSES,
    WORKFLOW_STATUSES,
)

# ---- 类型别名 ----

Handler = Callable[[dict, CoreWorkflowStep], Optional[dict]]
SlaCreator = Callable[[CoreWorkflowStep, dict, dict], Any]


class WorkflowError(Exception):
    """工作流业务错误。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """统一 aware/naive 时间（SQLite 回读为 naive）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _set_instance_status(db: Session, inst: CoreWorkflowInstance, status: str) -> None:
    if status not in WORKFLOW_STATUSES:
        raise WorkflowError(f"非法实例状态: {status}")
    inst.status = status
    if status in ("completed", "failed", "cancelled"):
        inst.end_time = _utcnow()


def _step_by_seq(steps: list[CoreWorkflowStep], seq: int) -> Optional[CoreWorkflowStep]:
    for s in steps:
        if s.seq == seq:
            return s
    return None


def _step_by_node_id(steps: list[CoreWorkflowStep], node_id: str) -> Optional[CoreWorkflowStep]:
    for s in steps:
        if s.config.get("id") == node_id:
            return s
    return None


# ---- 实例与步骤物化 ----


def _materialize_steps(
    db: Session, inst: CoreWorkflowInstance, defn: dict
) -> list[CoreWorkflowStep]:
    """按 DSL 节点物化步骤序列：顶层节点按序，parallel 分支展平为子步骤。"""
    steps: list[CoreWorkflowStep] = []
    seq = 0
    for node in defn["nodes"]:
        cfg = dict(node)
        if node["type"] == "retry" and node.get("target"):
            target = _find_handler(defn, node["target"])
            if target:
                cfg["_target_handler"] = target
        steps.append(
            CoreWorkflowStep(
                instance_id=inst.id,
                seq=seq,
                node_type=node["type"],
                name=node.get("name") or node["id"],
                config=cfg,
                status="pending",
            )
        )
        seq += 1
        if node["type"] == "parallel":
            for branch_idx, br in enumerate(node.get("branches", [])):
                for s in br.get("steps", []):
                    child_cfg = dict(s)
                    child_cfg["_branch_idx"] = branch_idx
                    child_cfg["_parent"] = node["id"]
                    steps.append(
                        CoreWorkflowStep(
                            instance_id=inst.id,
                            seq=seq,
                            node_type=s["type"],
                            name=s.get("name") or s["id"],
                            config=child_cfg,
                            status="pending",
                        )
                    )
                    seq += 1
    db.add_all(steps)
    db.flush()
    return steps


def _find_handler(defn: dict, node_id: str) -> Optional[str]:
    for n in defn["nodes"]:
        if n["id"] == node_id:
            return n.get("handler")
    return None


def create_instance(
    db: Session,
    defn: dict,
    *,
    title: Optional[str] = None,
    context: Optional[dict] = None,
    created_by: Optional[int] = None,
) -> CoreWorkflowInstance:
    """创建实例并物化全部步骤（状态 created，未启动）。"""
    defn = validate_definition(defn)
    inst = CoreWorkflowInstance(
        def_key=defn["key"],
        title=title or defn.get("name") or defn["key"],
        status="created",
        context=dict(context or {}),
        created_by=created_by,
    )
    db.add(inst)
    db.flush()
    _materialize_steps(db, inst, defn)
    db.commit()
    db.refresh(inst)
    return inst


def _steps(db: Session, instance_id: int) -> list[CoreWorkflowStep]:
    return list(
        db.execute(
            select(CoreWorkflowStep)
            .where(CoreWorkflowStep.instance_id == instance_id)
            .order_by(CoreWorkflowStep.seq)
        ).scalars()
    )


def get_instance(db: Session, instance_id: int) -> CoreWorkflowInstance:
    inst = db.get(CoreWorkflowInstance, instance_id)
    if inst is None:
        raise WorkflowError(f"工作流实例不存在: {instance_id}")
    return inst


# ---- 上下文与分支评估 ----


def _ctx_get(ctx: dict, path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _match_op(cur: Any, op: str, value: Any) -> bool:
    if op in ("eq", "=="):
        return cur == value
    if op in ("ne", "!="):
        return cur != value
    if op in ("gt", ">"):
        return cur is not None and cur > value
    if op in ("gte", ">="):
        return cur is not None and cur >= value
    if op in ("lt", "<"):
        return cur is not None and cur < value
    if op in ("lte", "<="):
        return cur is not None and cur <= value
    if op == "in":
        return isinstance(value, list) and cur in value
    if op == "contains":
        return isinstance(cur, list) and value in cur
    raise WorkflowError(f"未知条件操作符: {op}")


def _evaluate_branch(ctx: dict, config: dict) -> Optional[str]:
    """branch 节点：依 conditions 顺序求值，命中即返回 next，否则 default_next。"""
    for cond in config.get("conditions", []):
        matches = cond.get("match", [])
        if not matches:
            continue
        ok = all(
            _match_op(_ctx_get(ctx, m.get("path", "")), m.get("op", "eq"), m.get("value"))
            for m in matches
        )
        if ok:
            return cond.get("next")
    return config.get("default_next")


# ---- 步骤执行 ----


def _mark_step_started(step: CoreWorkflowStep) -> None:
    step.status = "running"
    step.started_at = _utcnow()


def _mark_step_completed(step: CoreWorkflowStep, payload: Optional[dict] = None) -> None:
    step.status = "completed"
    step.completed_at = _utcnow()
    if payload is not None:
        step.payload = payload


def _mark_step_skipped(step: CoreWorkflowStep) -> None:
    if step.status in ("pending", "running", "waiting"):
        step.status = "skipped"


def _mark_step_failed(step: CoreWorkflowStep, error: str) -> None:
    step.status = "failed"
    step.error = error
    step.completed_at = _utcnow()


def _invoke_handler(handler: Handler, ctx: dict, step: CoreWorkflowStep) -> Optional[dict]:
    """调用业务 handler：统一签名 handler(ctx, step) -> payload|None。"""
    return handler(ctx, step)


def _run_step(
    db: Session,
    inst: CoreWorkflowInstance,
    step: CoreWorkflowStep,
    ctx: dict,
    handlers: dict[str, Handler],
    sla_creator: Optional[SlaCreator],
) -> str:
    """执行单个步骤；返回 stopped|next|failed|waiting。

    步骤状态由本函数落库，实例 current_step 同步更新。
    """
    _mark_step_started(step)
    inst.current_step = step.seq
    node_type = step.node_type
    cfg = step.config or {}

    if node_type == "task":
        handler_name = cfg.get("handler")
        handler = handlers.get(handler_name)
        if handler is None:
            _mark_step_failed(step, f"未注册 handler: {handler_name}")
            inst.error = step.error
            return "failed"
        try:
            payload = _invoke_handler(handler, ctx, step)
            result = payload or {}
            merged = dict(ctx)
            if isinstance(result, dict):
                merged.update(result)
            _mark_step_completed(step, result if isinstance(result, dict) else {})
            ctx.clear()
            ctx.update(merged)
            if cfg.get("sla") and sla_creator is not None:
                sla_creator(step, cfg["sla"], ctx)
            return "next"
        except Exception as exc:  # noqa: BLE001
            return _fail_step(db, inst, step, cfg, ctx, exc)

    if node_type == "branch":
        target = _evaluate_branch(ctx, cfg)
        _mark_step_completed(step, {"chosen": target})
        if target:
            _jump_skip(steps_after=step, target_node_id=target)
            return "next"
        return "next"

    if node_type == "parallel":
        return _run_parallel(db, inst, step, ctx, handlers, sla_creator)

    if node_type == "wait":
        step.status = "waiting"
        step.completed_at = None
        inst.status = "waiting"
        timeout_minutes = cfg.get("timeout_minutes")
        info = {
            "wait_key": cfg.get("wait_key") or f"{inst.def_key}:{step.seq}",
            "assigned_to": cfg.get("assigned_to"),
            "confirm": cfg.get("confirm"),
            "timeout_next": cfg.get("timeout_next"),
        }
        if timeout_minutes:
            info["timeout_at"] = _utcnow().isoformat()
            info["timeout_minutes"] = timeout_minutes
        step.payload = info
        return "waiting"

    if node_type == "retry":
        return _run_retry(db, inst, step, ctx, handlers, sla_creator)

    _mark_step_failed(step, f"未知节点类型: {node_type}")
    return "failed"


def _run_parallel(
    db: Session,
    inst: CoreWorkflowInstance,
    step: CoreWorkflowStep,
    ctx: dict,
    handlers: dict[str, Handler],
    sla_creator: Optional[SlaCreator],
) -> str:
    """parallel：顺序执行本节点展平的子步骤，全部完成后推进 next。"""
    parent_id = step.config["id"]
    children = [
        s for s in _steps(db, inst.id) if (s.config or {}).get("_parent") == parent_id
    ]
    for child in children:
        if child.status in ("completed", "skipped", "failed"):
            continue
        result = _run_step(db, inst, child, ctx, handlers, sla_creator)
        if result == "waiting":
            return "waiting"
        if result == "failed":
            return "failed"
        if result != "next":
            return result
    _mark_step_completed(step, {"branches": len({c.config.get("_branch_idx") for c in children})})
    return "next"


def _run_retry(
    db: Session,
    inst: CoreWorkflowInstance,
    step: CoreWorkflowStep,
    ctx: dict,
    handlers: dict[str, Handler],
    sla_creator: Optional[SlaCreator],
) -> str:
    """retry：对 handler（或 target 解析的 handler）执行，失败按 max_attempts 重试。"""
    cfg = step.config or {}
    max_attempts = int(cfg.get("max_attempts") or 1)
    handler_name = cfg.get("handler") or cfg.get("_target_handler")
    handler = handlers.get(handler_name) if handler_name else None
    if handler is None:
        _mark_step_failed(step, f"retry 未注册 handler: {handler_name}")
        return "failed"
    for attempt in range(1, max_attempts + 1):
        try:
            payload = _invoke_handler(handler, ctx, step) or {}
            merged = dict(ctx)
            if isinstance(payload, dict):
                merged.update(payload)
            _mark_step_completed(
                step,
                {"attempts": attempt, "payload": payload if isinstance(payload, dict) else {}},
            )
            ctx.clear()
            ctx.update(merged)
            return "next"
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    return _fail_step(db, inst, step, cfg, ctx, last_error)


def _fail_step(
    db: Session,
    inst: CoreWorkflowInstance,
    step: CoreWorkflowStep,
    cfg: dict,
    ctx: dict,
    exc: Exception,
) -> str:
    """步骤失败：优先执行 compensate 补偿，无补偿则标记人工介入。"""
    compensate_name = cfg.get("compensate")
    compensated = False
    if compensate_name:
        comp = _compensate_handlers.get(compensate_name)
        if comp is not None:
            try:
                comp(ctx, step)
                compensated = True
            except Exception:  # noqa: BLE001
                compensated = False
    _mark_step_failed(step, str(exc))
    if compensated:
        step.payload = {**(step.payload or {}), "compensated": True}
        _set_instance_status(db, inst, "failed")
    else:
        step.payload = {**(step.payload or {}), "manual_intervention": True}
        _set_instance_status(db, inst, "failed")
    return "failed"


# 补偿 handler 注册表：由调用方通过 register_compensate 登记
_compensate_handlers: dict[str, Handler] = {}


def register_compensate(name: str, handler: Handler) -> None:
    """注册补偿 handler（签名同业务 handler：handler(ctx, step)）。"""
    _compensate_handlers[name] = handler


def _jump_skip(steps_after: CoreWorkflowStep, target_node_id: str) -> None:
    """branch 跳转：由调用方在执行序列中跳过目标节点之前的未完成步骤。

    引擎推进循环会按 seq 顺序执行；branch 选择 target 后，若 target 不在
    紧邻位置，由循环层的跳过逻辑处理（见 _advance_loop）。
    """
    # 占位：真正的跳过逻辑在 _advance_loop 中以“当前待执行节点由
    # branch.payload['chosen'] 决定”的方式实现。
    return None


# ---- 推进循环 ----


def _advance_loop(
    db: Session,
    inst: CoreWorkflowInstance,
    steps: list[CoreWorkflowStep],
    handlers: dict[str, Handler],
    sla_creator: Optional[SlaCreator],
) -> str:
    """按 seq 顺序推进；遇 waiting 停、失败停、全部完成置 completed。"""
    ctx = dict(inst.context or {})
    for step in steps:
        if step.status in ("completed", "skipped", "failed"):
            if step.status == "failed":
                if not inst.error:
                    inst.error = step.error
                _set_instance_status(db, inst, "failed")
                return "failed"
            continue
        if step.status == "waiting":
            inst.context = ctx
            inst.status = "waiting"
            return "waiting"

        result = _run_step(db, inst, step, ctx, handlers, sla_creator)
        db.flush()
        if result == "waiting":
            inst.context = ctx
            inst.status = "waiting"
            return "waiting"
        if result == "failed":
            inst.context = ctx
            if not inst.error:
                inst.error = step.error
            # 失败后：后续未执行的步骤全部标记跳过
            for s in steps:
                if s.seq > step.seq and s.status in ("pending", "running"):
                    _mark_step_skipped(s)
            _set_instance_status(db, inst, "failed")
            return "failed"

        # branch 选择目标后，跳过不在目标可达链上的中间/后续节点
        if step.node_type == "branch" and step.status == "completed":
            chosen = (step.payload or {}).get("chosen")
            if chosen:
                reachable = _collect_reachable(steps, chosen)
                if reachable is None:
                    _set_instance_status(db, inst, "failed")
                    step.error = f"branch 目标节点不存在: {chosen}"
                    step.status = "failed"
                    inst.error = step.error
                    return "failed"
                for s in steps:
                    if s.seq > step.seq and s.status in ("pending", "running"):
                        if (s.config or {}).get("id") not in reachable:
                            _mark_step_skipped(s)

    inst.context = ctx
    _set_instance_status(db, inst, "completed")
    return "completed"


def _collect_reachable(
    steps: list[CoreWorkflowStep], start_node_id: str
) -> Optional[set[str]]:
    """收集从 start 起沿 next 链可达的节点 id 集合；节点缺失返回 None，防环。"""
    reachable: set[str] = set()
    cur: Optional[str] = start_node_id
    guard = 0
    while cur and guard <= len(steps):
        ns = _step_by_node_id(steps, cur)
        if ns is None:
            return None
        if cur in reachable:
            break
        reachable.add(cur)
        cur = (ns.config or {}).get("next")
        guard += 1
    return reachable


def run(
    db: Session,
    instance_id: int,
    *,
    handlers: Optional[dict[str, Handler]] = None,
    sla_creator: Optional[SlaCreator] = None,
) -> CoreWorkflowInstance:
    """启动/续跑实例：状态 created/running 时推进，返回最新实例状态。"""
    inst = get_instance(db, instance_id)
    if inst.status in ("completed", "failed", "cancelled"):
        return inst
    if inst.status == "created":
        _set_instance_status(db, inst, "running")
        inst.start_time = _utcnow()
    db.flush()
    steps = _steps(db, instance_id)
    result = _advance_loop(db, inst, steps, handlers or {}, sla_creator)
    db.commit()
    db.refresh(inst)
    return inst


# ---- 人工节点（wait） ----


def _resolve_wait_step(db: Session, instance_id: int, seq: int) -> CoreWorkflowStep:
    inst = get_instance(db, instance_id)
    steps = _steps(db, instance_id)
    step = _step_by_seq(steps, seq)
    if step is None or step.instance_id != inst.id:
        raise WorkflowError(f"步骤不存在: instance={instance_id} seq={seq}")
    return step


def confirm_wait_step(
    db: Session,
    instance_id: int,
    seq: int,
    *,
    actor_id: Optional[int] = None,
    payload: Optional[dict] = None,
    handlers: Optional[dict[str, Handler]] = None,
    sla_creator: Optional[SlaCreator] = None,
) -> CoreWorkflowInstance:
    """人工确认 wait 步骤：置 completed，写入确认信息，按 confirm 继续推进。"""
    step = _resolve_wait_step(db, instance_id, seq)
    if step.status != "waiting":
        raise WorkflowError(f"步骤 {seq} 非 waiting 状态: {step.status}")
    _mark_step_completed(
        step,
        {
            **dict(step.payload or {}),
            "confirmed": True,
            "confirmed_by": actor_id,
            "confirmed_at": _utcnow().isoformat(),
            "confirm_payload": payload or {},
        },
    )
    inst = get_instance(db, instance_id)
    if step.config.get("confirm"):
        target = _step_by_node_id(_steps(db, instance_id), step.config["confirm"])
        if target is None:
            _set_instance_status(db, inst, "failed")
            step.error = f"wait 确认目标不存在: {step.config['confirm']}"
            db.commit()
            db.refresh(inst)
            return inst
        for s in _steps(db, instance_id):
            if s.seq > step.seq and s.seq < target.seq:
                _mark_step_skipped(s)
    return run(db, instance_id, handlers=handlers or {}, sla_creator=sla_creator)


def timeout_wait_step(
    db: Session,
    instance_id: int,
    seq: int,
    *,
    handlers: Optional[dict[str, Handler]] = None,
    sla_creator: Optional[SlaCreator] = None,
) -> CoreWorkflowInstance:
    """wait 超时兜底：置 completed 并标记 timeout，按 timeout_next 继续推进。"""
    step = _resolve_wait_step(db, instance_id, seq)
    if step.status != "waiting":
        raise WorkflowError(f"步骤 {seq} 非 waiting 状态: {step.status}")
    _mark_step_completed(
        step,
        {
            **dict(step.payload or {}),
            "timeout": True,
            "timeout_at": _utcnow().isoformat(),
        },
    )
    inst = get_instance(db, instance_id)
    if step.config.get("timeout_next"):
        target = _step_by_node_id(_steps(db, instance_id), step.config["timeout_next"])
        if target is None:
            _set_instance_status(db, inst, "failed")
            step.error = f"wait 超时目标不存在: {step.config['timeout_next']}"
            db.commit()
            db.refresh(inst)
            return inst
        for s in _steps(db, instance_id):
            if s.seq > step.seq and s.seq < target.seq:
                _mark_step_skipped(s)
    return run(db, instance_id, handlers=handlers or {}, sla_creator=sla_creator)


def scan_waiting_timeouts(
    db: Session,
    now: Optional[datetime] = None,
    *,
    handlers: Optional[dict[str, Handler]] = None,
    sla_creator: Optional[SlaCreator] = None,
) -> int:
    """扫描超时待办并执行 timeout 兜底，返回处理的步骤数（调度侧批量调用）。"""
    now = _as_utc(now) or _utcnow()
    steps = list(
        db.execute(
            select(CoreWorkflowStep).where(CoreWorkflowStep.status == "waiting")
        ).scalars()
    )
    handled = 0
    for step in steps:
        info = step.payload or {}
        if not info.get("timeout_at"):
            continue
        try:
            timeout_at = datetime.fromisoformat(info["timeout_at"])
        except ValueError:
            continue
        if _as_utc(timeout_at) <= now:
            timeout_wait_step(
                db, step.instance_id, step.seq, handlers=handlers, sla_creator=sla_creator
            )
            handled += 1
    return handled


# ---- 实例生命周期 ----


def pause_instance(db: Session, instance_id: int, reason: Optional[str] = None) -> CoreWorkflowInstance:
    inst = get_instance(db, instance_id)
    if inst.status not in ("created", "running", "waiting"):
        raise WorkflowError(f"状态 {inst.status} 不可暂停")
    inst.status = "paused"
    inst.error = reason
    db.commit()
    db.refresh(inst)
    return inst


def resume_instance(
    db: Session,
    instance_id: int,
    *,
    handlers: Optional[dict[str, Handler]] = None,
    sla_creator: Optional[SlaCreator] = None,
) -> CoreWorkflowInstance:
    inst = get_instance(db, instance_id)
    if inst.status != "paused":
        raise WorkflowError(f"状态 {inst.status} 不可恢复")
    return run(db, instance_id, handlers=handlers or {}, sla_creator=sla_creator)


def cancel_instance(db: Session, instance_id: int, reason: Optional[str] = None) -> CoreWorkflowInstance:
    inst = get_instance(db, instance_id)
    if inst.status in ("completed", "failed", "cancelled"):
        raise WorkflowError(f"状态 {inst.status} 不可取消")
    for s in _steps(db, instance_id):
        if s.status in ("pending", "running"):
            _mark_step_skipped(s)
    inst.status = "cancelled"
    inst.end_time = _utcnow()
    inst.error = reason
    db.commit()
    db.refresh(inst)
    return inst


# ---- 查询 ----


def list_waiting_steps(
    db: Session,
    *,
    wait_key: Optional[str] = None,
    assigned_to: Optional[int] = None,
) -> list[CoreWorkflowStep]:
    """待办查询：全部 waiting 步骤，可按 wait_key / assigned_to 过滤。

    JSON 字段过滤在 Python 端完成，兼容 SQLite / PostgreSQL。
    """
    steps = list(
        db.execute(
            select(CoreWorkflowStep)
            .where(CoreWorkflowStep.status == "waiting")
            .order_by(CoreWorkflowStep.seq)
        ).scalars()
    )
    result = []
    for s in steps:
        cfg = s.config or {}
        if wait_key and cfg.get("wait_key") != wait_key:
            continue
        if assigned_to is not None and cfg.get("assigned_to") != assigned_to:
            continue
        result.append(s)
    return result


def step_status_counts(db: Session, instance_id: int) -> dict[str, int]:
    """实例步骤状态统计（进度看板）。"""
    counts = {s: 0 for s in WORKFLOW_STEP_STATUSES}
    for s in _steps(db, instance_id):
        counts[s.status] = counts.get(s.status, 0) + 1
    return counts
