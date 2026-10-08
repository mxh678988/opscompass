"""插件 SDK 异常定义。

SDK 对外发布，不依赖内核内部实现；异常层级保持稳定，属于接口承诺的一部分。
"""

from __future__ import annotations


class SdkError(Exception):
    """SDK 异常基类。"""


class NamespaceViolation(SdkError):
    """插件越出自身命名空间（事件名、表前缀、权限点等）。"""

    def __init__(self, plugin_id: str, what: str, value: str, allow: str) -> None:
        self.plugin_id = plugin_id
        self.what = what
        self.value = value
        self.allow = allow
        super().__init__(
            f"插件 {plugin_id} 的 {what} {value!r} 越界：仅允许 {allow}"
        )


class NotAvailableError(SdkError):
    """接口已冻结但对应内核能力尚未落地（分期实现）。"""

    def __init__(self, feature: str, planned_in: str) -> None:
        self.feature = feature
        self.planned_in = planned_in
        super().__init__(f"{feature} 尚未启用，计划在 {planned_in} 落地")


class ManifestError(SdkError):
    """插件清单校验失败。"""

    def __init__(self, field: str, detail: str) -> None:
        self.field = field
        self.detail = detail
        super().__init__(f"清单字段 {field} 校验失败：{detail}")
