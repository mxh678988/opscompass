"""AI 模型统一客户端：api（云端 OpenAI 兼容）/ local（Ollama）双模式。

对外只暴露 `LLMClient.chat()`，上层（分析器 / 定级器 / 治理器）不感知模式差异。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.core.config import settings

# 送模型的消息结构：{"role": "system|user|assistant", "content": "..."}
Message = dict[str, str]


class LLMError(RuntimeError):
    """模型调用失败（网络 / 鉴权 / 超时 / 响应异常）。"""


@dataclass
class LLMResult:
    """模型调用结果。"""

    text: str
    mode: str
    model: str
    duration_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def extract_json(text: str) -> Optional[dict]:
    """从模型输出中宽松提取 JSON 对象。

    兼容三类输出：纯 JSON、```json 代码块、前后夹杂说明文字。
    """
    if not text:
        return None
    candidates: list[str] = []
    fenced = re.findall(r"```(?:json)?\s*(.+?)```", text, flags=re.S)
    candidates.extend(fenced)
    candidates.append(text)
    for raw in candidates:
        raw = raw.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


class LLMClient:
    """按当前配置的模式调用模型。"""

    def __init__(self, mode: Optional[str] = None, model: Optional[str] = None) -> None:
        self.mode = (mode or settings.ai_mode).strip().lower()
        if self.mode not in ("api", "local"):
            self.mode = "local"
        self.model = model or (
            settings.AI_API_MODEL if self.mode == "api" else settings.AI_LOCAL_MODEL
        )
        self.base_url = (
            settings.AI_API_BASE_URL if self.mode == "api" else settings.AI_LOCAL_BASE_URL
        ).rstrip("/")

    # ------------------------------------------------------------ 内部
    def _client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {"timeout": settings.AI_TIMEOUT}
        if settings.AI_PROXY:
            kwargs["proxy"] = settings.AI_PROXY
        return httpx.Client(**kwargs)

    def _headers(self) -> dict[str, str]:
        if self.mode == "api":
            return {
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            }
        return {"Content-Type": "application/json"}

    def _endpoint(self) -> str:
        if self.mode == "api":
            return f"{self.base_url}/chat/completions"
        # Ollama 原生对话接口
        return f"{self.base_url}/api/chat"

    def _payload(self, messages: list[Message], temperature: float, max_tokens: int) -> dict:
        if self.mode == "api":
            return {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

    @staticmethod
    def _parse_response(mode: str, data: dict) -> tuple[str, int, int]:
        if mode == "api":
            choices = data.get("choices") or []
            text = ""
            if choices:
                text = (choices[0].get("message") or {}).get("content") or ""
            usage = data.get("usage") or {}
            return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        message = data.get("message") or {}
        text = message.get("content") or ""
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        return text, prompt_tokens, completion_tokens

    # ------------------------------------------------------------ 对外
    def readiness(self) -> dict[str, Any]:
        """模式可用性探测：api 校验 Key，local 校验服务与模型是否就绪。"""
        info: dict[str, Any] = {
            "mode": self.mode,
            "model": self.model,
            "base_url": self.base_url,
            "enabled": settings.AI_ENABLED,
            "ok": False,
            "message": "",
            "models": [],
        }
        if not settings.AI_ENABLED:
            info["message"] = "AI 功能已关闭（AI_ENABLED=false）"
            return info
        if self.mode == "api":
            if not settings.AI_API_KEY:
                info["message"] = "未配置 AI_API_KEY，API 模式不可用"
                return info
            info["ok"] = True
            info["message"] = "API 模式就绪（未发起探测请求）"
            return info

        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            info["message"] = f"本地模型服务不可达：{exc}"
            return info

        names = [m.get("name", "") for m in (data.get("models") or [])]
        info["models"] = names
        if self.model in names or any(n.split(":")[0] == self.model.split(":")[0] for n in names):
            info["ok"] = True
            info["message"] = "本地模型服务就绪"
        else:
            info["message"] = f"服务可达但未找到模型 {self.model}，可用：{', '.join(names[:8])}"
        return info

    def chat(
        self,
        messages: list[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResult:
        """发起一次对话补全，失败统一抛 LLMError。"""
        if not settings.AI_ENABLED:
            raise LLMError("AI 功能已关闭（AI_ENABLED=false）")
        if self.mode == "api" and not settings.AI_API_KEY:
            raise LLMError("API 模式缺少 AI_API_KEY，请在 .env 中配置或切换为 local 模式")

        payload = self._payload(
            messages,
            temperature if temperature is not None else settings.AI_TEMPERATURE,
            max_tokens or settings.AI_MAX_TOKENS,
        )
        started = time.perf_counter()
        try:
            with self._client() as client:
                resp = client.post(self._endpoint(), json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            raise LLMError(f"模型返回 HTTP {exc.response.status_code}：{body}") from exc
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型调用失败（{self.mode} 模式，{self.base_url}）：{exc}") from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        text, prompt_tokens, completion_tokens = self._parse_response(self.mode, data)
        if not text.strip():
            raise LLMError("模型返回空内容")
        return LLMResult(
            text=text.strip(),
            mode=self.mode,
            model=self.model,
            duration_ms=duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw=data if isinstance(data, dict) else {},
        )
