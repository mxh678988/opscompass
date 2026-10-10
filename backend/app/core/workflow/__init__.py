"""OS 内核 · 工作流引擎（M5）。

对外导出：
- ``dsl``：流程定义解析与校验（YAML/JSON），节点类型 task/branch/parallel/wait/retry；
- ``engine``：运行态引擎，状态机驱动、幂等推进、人工节点与超时兜底、失败补偿、
  可选挂接 M4 SLA。
"""

from app.core.workflow import dsl, engine
from app.core.workflow.dsl import (
    NODE_BRANCH,
    NODE_PARALLEL,
    NODE_RETRY,
    NODE_TASK,
    NODE_WAIT,
    NODE_TYPES,
    WorkflowDSLError,
    find_node,
    node_ids,
    parse_definition,
    validate_definition,
)
from app.core.workflow.engine import (
    SlaCreator,
    WorkflowError,
    cancel_instance,
    confirm_wait_step,
    create_instance,
    get_instance,
    list_waiting_steps,
    pause_instance,
    register_compensate,
    resume_instance,
    run,
    scan_waiting_timeouts,
    step_status_counts,
    timeout_wait_step,
)

__all__ = [
    "dsl",
    "engine",
    "NODE_TASK",
    "NODE_BRANCH",
    "NODE_PARALLEL",
    "NODE_WAIT",
    "NODE_RETRY",
    "NODE_TYPES",
    "WorkflowDSLError",
    "WorkflowError",
    "validate_definition",
    "parse_definition",
    "find_node",
    "node_ids",
    "create_instance",
    "run",
    "confirm_wait_step",
    "timeout_wait_step",
    "scan_waiting_timeouts",
    "pause_instance",
    "resume_instance",
    "cancel_instance",
    "get_instance",
    "list_waiting_steps",
    "step_status_counts",
    "register_compensate",
    "SlaCreator",
]
