"""OS 内核 · 工作流 DSL（M5）：定义解析与校验。

流程定义支持 YAML/JSON 文本或 Python dict，节点类型：
- ``task``      执行单元（handler 必填）
- ``branch``    条件分支（conditions + default_next）
- ``parallel``  并行（branches，每条分支为步骤序列）
- ``wait``      人工节点（等待事件/审批，可设 timeout_next 兜底）
- ``retry``     重试（target 指向被重试节点，max_attempts）

示例（JSON）：
    {
      "key": "collect_label_stats",
      "name": "数据采集→打标→统计",
      "nodes": [
        {"id": "collect", "type": "task", "name": "数据采集", "handler": "collect_data", "next": "label"},
        {"id": "label", "type": "task", "name": "打标", "handler": "label_data", "next": "stats"},
        {"id": "stats", "type": "task", "name": "统计", "handler": "stats_data"}
      ]
    }
"""

from __future__ import annotations

import json
from typing import Any, Optional

# 节点类型
NODE_TASK = "task"
NODE_BRANCH = "branch"
NODE_PARALLEL = "parallel"
NODE_WAIT = "wait"
NODE_RETRY = "retry"

NODE_TYPES = (NODE_TASK, NODE_BRANCH, NODE_PARALLEL, NODE_WAIT, NODE_RETRY)


class WorkflowDSLError(ValueError):
    """DSL 定义非法。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise WorkflowDSLError(msg)


def _validate_node(node: dict, node_ids: set[str]) -> None:
    _require("id" in node and isinstance(node["id"], str) and node["id"], "节点缺少非空 id")
    _require(node["id"] not in node_ids, f"节点 id 重复: {node['id']}")
    _require(node.get("type") in NODE_TYPES, f"节点 {node['id']} 类型非法: {node.get('type')}")
    node_ids.add(node["id"])

    ntype = node["type"]
    if ntype == NODE_TASK:
        _require(node.get("handler"), f"task 节点 {node['id']} 缺少 handler")
    elif ntype == NODE_BRANCH:
        _require(node.get("conditions") and isinstance(node["conditions"], list), f"branch 节点 {node['id']} 缺少 conditions 列表")
        for c in node["conditions"]:
            _require(isinstance(c, dict) and "next" in c, f"branch 节点 {node['id']} 条件缺少 next")
        _require(node.get("default_next"), f"branch 节点 {node['id']} 缺少 default_next")
    elif ntype == NODE_PARALLEL:
        _require(node.get("branches") and isinstance(node["branches"], list), f"parallel 节点 {node['id']} 缺少 branches 列表")
        for br in node["branches"]:
            _require(isinstance(br, dict) and isinstance(br.get("steps", []), list) and br["steps"], f"parallel 分支非法: {node['id']}")
            for s in br["steps"]:
                _validate_node(s, node_ids)
    elif ntype == NODE_WAIT:
        # wait 节点必须提供确认目标或超时兜底
        _require(node.get("confirm") or node.get("timeout_next"), f"wait 节点 {node['id']} 缺少 confirm/timeout_next")
    elif ntype == NODE_RETRY:
        _require(node.get("max_attempts") and int(node["max_attempts"]) >= 1, f"retry 节点 {node['id']} 缺少有效 max_attempts")
        _require(node.get("target") or node.get("handler"), f"retry 节点 {node['id']} 缺少 target/handler")


def _check_next_refs(nodes: list[dict], node_ids: set[str]) -> None:
    """校验 next 引用都存在。"""
    for n in nodes:
        for field in ("next", "default_next", "timeout_next", "confirm"):
            ref = n.get(field)
            if ref and ref not in node_ids:
                raise WorkflowDSLError(f"节点 {n['id']} 的 {field} 引用不存在: {ref}")
        for c in n.get("conditions", []):
            if c.get("next") and c["next"] not in node_ids:
                raise WorkflowDSLError(f"节点 {n['id']} 条件 next 引用不存在: {c['next']}")


def validate_definition(defn: dict) -> dict:
    """校验流程定义并返回规范化副本（节点 id 去重、引用检查）。"""
    _require(isinstance(defn, dict), "流程定义必须是对象")
    _require(defn.get("key"), "流程定义缺少 key")
    _require(defn.get("nodes") and isinstance(defn["nodes"], list), "流程定义缺少 nodes")
    _require(len(defn["nodes"]) > 0, "流程定义 nodes 为空")

    node_ids: set[str] = set()
    for n in defn["nodes"]:
        _validate_node(n, node_ids)
    _check_next_refs(defn["nodes"], node_ids)
    return defn


def parse_definition(source: str | dict, *, fmt: str = "json") -> dict:
    """从 JSON 文本或 dict 解析并校验流程定义。"""
    if isinstance(source, dict):
        return validate_definition(source)
    text = source.strip()
    if fmt == "yaml":
        try:
            import yaml  # 可选依赖

            data = yaml.safe_load(text)
        except ImportError as exc:  # pragma: no cover
            raise WorkflowDSLError("解析 YAML 需要安装 PyYAML") from exc
    else:
        data = json.loads(text)
    return validate_definition(data)


def node_ids(defn: dict) -> list[str]:
    """返回顶层节点 id 序列（parallel 内嵌节点不计入）。"""
    return [n["id"] for n in defn["nodes"]]


def find_node(defn: dict, node_id: str) -> Optional[dict]:
    """按 id 查找顶层节点。"""
    for n in defn["nodes"]:
        if n["id"] == node_id:
            return n
    return None
