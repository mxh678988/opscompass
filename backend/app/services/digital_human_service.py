"""数字人一键生成服务：形象库 / 音色库 / 项目 / 四阶段生成编排 / 工作流模板。

一键生成链路（四阶段）：
1) script  口播稿：LLM 依据主题与素材产出分镜口播稿；模型不可用时降级为模板化切分。
2) voice   AI 配音：按音色配置调用 TTS 引擎；引擎缺失时标记演练并给出对接提示。
3) avatar  数字人驱动：按形象配置调用口型驱动引擎，产出数字人视频片段。
4) compose 成片合成：叠加字幕 / BGM 输出目标分辨率的成品短视频。

引擎可用性由 `engine_status()` 实时探测，任一阶段缺引擎则该阶段以 simulated 模式留痕，
不会中断整体流程，保证「一键生成」在无 GPU 环境下仍可完整跑通并暴露对接点。
"""

from __future__ import annotations

import importlib.util
import time
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.digital_human import (
    DH_STAGES,
    DhAvatar,
    DhProject,
    DhTask,
    DhVoice,
    DhWorkflow,
)

# 阶段中文名
STAGE_NAMES = {
    "script": "口播稿生成",
    "voice": "AI 配音",
    "avatar": "数字人驱动",
    "compose": "成片合成",
}
# 默认工作流编排
DEFAULT_STEPS = [
    {"stage": "script", "name": "口播稿生成", "engine": "llm", "enabled": True},
    {"stage": "voice", "name": "AI 配音", "engine": "edge-tts", "enabled": True},
    {"stage": "avatar", "name": "数字人驱动", "engine": "comfyui", "enabled": True},
    {"stage": "compose", "name": "成片合成", "engine": "ffmpeg", "enabled": True},
]


def _now() -> datetime:
    return datetime.now()


def _t(value: Any, default: str = "") -> str:
    return (value or "").strip() if isinstance(value, str) else default


def _paginate(
    db: Session, model, conditions: list, page: int = 1, size: int = 20, order_by=None
) -> tuple[int, list]:
    """通用分页查询，返回 (total, rows)。"""
    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    total = db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    order = order_by if order_by is not None else model.id.desc()
    if not isinstance(order, (tuple, list)):
        order = [order]
    rows = (
        db.execute(
            select(model).where(*conditions).order_by(*order).offset((page - 1) * size).limit(size)
        )
        .scalars()
        .all()
    )
    return int(total), list(rows)


# ============================================================ 引擎探测
def engine_status() -> dict:
    """探测各生成阶段可用引擎（无副作用，供前端展示对接状态）。"""
    voice_engine = ""
    for module, label in (("edge_tts", "edge-tts"), ("TTS", "coqui-tts"), ("cosyvoice", "cosyvoice")):
        if importlib.util.find_spec(module) is not None:
            voice_engine = label
            break

    from app.core.config import settings

    avatar_endpoint = _t(getattr(settings, "DH_AVATAR_ENDPOINT", "")) or "http://127.0.0.1:8188"
    avatar_engine = _t(getattr(settings, "DH_AVATAR_ENGINE", "")) or "comfyui"

    return {
        "script": {"engine": "llm", "ready": bool(getattr(settings, "AI_ENABLED", False)), "detail": "由 AI 模型中心统一提供"},
        "voice": {"engine": voice_engine or "edge-tts", "ready": bool(voice_engine), "detail": "" if voice_engine else "未检测到本地 TTS 库，将以演练模式留痕"},
        "avatar": {"engine": avatar_engine, "endpoint": avatar_endpoint, "ready": False, "detail": "需本机 ComfyUI/口型驱动服务可达"},
        "compose": {"engine": "ffmpeg", "ready": importlib.util.find_spec("subprocess") is not None, "detail": "成片合成依赖 ffmpeg"},
    }


# ============================================================ 形象库
def avatar_to_dict(row: DhAvatar) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name,
        "avatar_type": row.avatar_type, "gender": row.gender, "style": row.style,
        "preview_url": row.preview_url, "source_url": row.source_url,
        "engine": row.engine, "status": row.status, "remark": row.remark,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def list_avatars(db: Session, tenant_id: int, keyword: str | None = None, avatar_type: str | None = None,
                 page: int = 1, size: int = 50) -> dict:
    conds = [DhAvatar.tenant_id == tenant_id]
    if keyword:
        conds.append(or_(DhAvatar.name.like(f"%{keyword}%"), DhAvatar.style.like(f"%{keyword}%")))
    if avatar_type:
        conds.append(DhAvatar.avatar_type == avatar_type)
    total, rows = _paginate(db, DhAvatar, conds, page, size, order_by=DhAvatar.id.desc())
    return {"total": total, "page": page, "size": size, "items": [avatar_to_dict(r) for r in rows]}


def create_avatar(db: Session, tenant_id: int, payload: Any) -> dict:
    name = _t(getattr(payload, "name", ""))
    if not name:
        raise ValueError("形象名称不能为空")
    existed = db.execute(
        select(DhAvatar).where(DhAvatar.tenant_id == tenant_id, DhAvatar.name == name)
    ).scalars().first()
    if existed is not None:
        raise ValueError(f"形象「{name}」已存在")
    row = DhAvatar(
        tenant_id=tenant_id, name=name,
        avatar_type=_t(getattr(payload, "avatar_type", "preset")) or "preset",
        gender=_t(getattr(payload, "gender", "neutral")) or "neutral",
        style=_t(getattr(payload, "style", "")),
        preview_url=_t(getattr(payload, "preview_url", "")),
        source_url=_t(getattr(payload, "source_url", "")),
        engine=_t(getattr(payload, "engine", "")),
        status=_t(getattr(payload, "status", "ready")) or "ready",
        remark=_t(getattr(payload, "remark", "")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return avatar_to_dict(row)


def update_avatar(db: Session, tenant_id: int, avatar_id: int, payload: Any) -> dict:
    row = db.get(DhAvatar, avatar_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("形象不存在")
    for field in ("name", "avatar_type", "gender", "style", "preview_url", "source_url",
                  "engine", "status", "remark"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return avatar_to_dict(row)


def delete_avatar(db: Session, tenant_id: int, avatar_id: int) -> dict:
    row = db.get(DhAvatar, avatar_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("形象不存在")
    db.delete(row)
    db.commit()
    return {"id": avatar_id, "deleted": True}


# ============================================================ 音色库
def voice_to_dict(row: DhVoice) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name, "engine": row.engine,
        "voice_id": row.voice_id, "language": row.language, "gender": row.gender,
        "speed": row.speed, "sample_url": row.sample_url, "status": row.status,
        "remark": row.remark, "created_at": row.created_at, "updated_at": row.updated_at,
    }


def list_voices(db: Session, tenant_id: int, keyword: str | None = None, engine: str | None = None,
                page: int = 1, size: int = 50) -> dict:
    conds = [DhVoice.tenant_id == tenant_id]
    if keyword:
        conds.append(DhVoice.name.like(f"%{keyword}%"))
    if engine:
        conds.append(DhVoice.engine == engine)
    total, rows = _paginate(db, DhVoice, conds, page, size, order_by=DhVoice.id.desc())
    return {"total": total, "page": page, "size": size, "items": [voice_to_dict(r) for r in rows]}


def create_voice(db: Session, tenant_id: int, payload: Any) -> dict:
    name = _t(getattr(payload, "name", ""))
    if not name:
        raise ValueError("音色名称不能为空")
    existed = db.execute(
        select(DhVoice).where(DhVoice.tenant_id == tenant_id, DhVoice.name == name)
    ).scalars().first()
    if existed is not None:
        raise ValueError(f"音色「{name}」已存在")
    row = DhVoice(
        tenant_id=tenant_id, name=name,
        engine=_t(getattr(payload, "engine", "edge-tts")) or "edge-tts",
        voice_id=_t(getattr(payload, "voice_id", "")),
        language=_t(getattr(payload, "language", "zh-CN")) or "zh-CN",
        gender=_t(getattr(payload, "gender", "neutral")) or "neutral",
        speed=_t(getattr(payload, "speed", "1.0")) or "1.0",
        sample_url=_t(getattr(payload, "sample_url", "")),
        status=_t(getattr(payload, "status", "ready")) or "ready",
        remark=_t(getattr(payload, "remark", "")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return voice_to_dict(row)


def update_voice(db: Session, tenant_id: int, voice_id: int, payload: Any) -> dict:
    row = db.get(DhVoice, voice_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("音色不存在")
    for field in ("name", "engine", "voice_id", "language", "gender", "speed",
                  "sample_url", "status", "remark"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return voice_to_dict(row)


def delete_voice(db: Session, tenant_id: int, voice_id: int) -> dict:
    row = db.get(DhVoice, voice_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("音色不存在")
    db.delete(row)
    db.commit()
    return {"id": voice_id, "deleted": True}


# ============================================================ 项目
def task_to_dict(row: DhTask) -> dict:
    return {
        "id": row.id, "project_id": row.project_id, "stage": row.stage,
        "stage_name": row.stage_name or STAGE_NAMES.get(row.stage, row.stage),
        "seq": row.seq, "status": row.status, "progress": row.progress,
        "engine": row.engine, "input_brief": row.input_brief,
        "output_url": row.output_url, "output_text": row.output_text,
        "message": row.message, "duration_ms": row.duration_ms,
        "started_at": row.started_at, "finished_at": row.finished_at,
    }


def project_to_dict(row: DhProject, with_tasks: bool = False) -> dict:
    data = {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name, "topic": row.topic,
        "source_text": row.source_text, "script": row.script, "segments": row.segments or [],
        "avatar_id": row.avatar_id, "voice_id": row.voice_id, "workflow_id": row.workflow_id,
        "resolution": row.resolution, "aspect_ratio": row.aspect_ratio,
        "duration_sec": row.duration_sec, "subtitle_enabled": row.subtitle_enabled,
        "bgm": row.bgm, "status": row.status, "progress": row.progress,
        "video_url": row.video_url, "audio_url": row.audio_url, "cover_url": row.cover_url,
        "simulated": row.simulated, "ai_model": row.ai_model, "error": row.error,
        "remark": row.remark, "created_at": row.created_at, "updated_at": row.updated_at,
    }
    if with_tasks:
        data["tasks"] = [task_to_dict(t) for t in row.tasks]
    return data


def list_projects(db: Session, tenant_id: int, keyword: str | None = None, status: str | None = None,
                  page: int = 1, size: int = 20) -> dict:
    conds = [DhProject.tenant_id == tenant_id]
    if keyword:
        conds.append(or_(DhProject.name.like(f"%{keyword}%"), DhProject.topic.like(f"%{keyword}%")))
    if status:
        conds.append(DhProject.status == status)
    total, rows = _paginate(db, DhProject, conds, page, size, order_by=DhProject.id.desc())
    return {"total": total, "page": page, "size": size, "items": [project_to_dict(r) for r in rows]}


def get_project(db: Session, tenant_id: int, project_id: int) -> Optional[DhProject]:
    row = db.get(DhProject, project_id)
    if row is None or row.tenant_id != tenant_id:
        return None
    return row


def create_project(db: Session, tenant_id: int, payload: Any) -> dict:
    name = _t(getattr(payload, "name", ""))
    if not name:
        raise ValueError("项目名称不能为空")
    workflow_id = getattr(payload, "workflow_id", None)
    if workflow_id is None:
        workflow_id = ensure_default_workflow(db, tenant_id).id
    row = DhProject(
        tenant_id=tenant_id, name=name,
        topic=_t(getattr(payload, "topic", "")),
        source_text=_t(getattr(payload, "source_text", "")),
        avatar_id=getattr(payload, "avatar_id", None),
        voice_id=getattr(payload, "voice_id", None),
        workflow_id=workflow_id,
        resolution=_t(getattr(payload, "resolution", "720x1280")) or "720x1280",
        aspect_ratio=_t(getattr(payload, "aspect_ratio", "9:16")) or "9:16",
        duration_sec=int(getattr(payload, "duration_sec", 0) or 0),
        subtitle_enabled=bool(getattr(payload, "subtitle_enabled", True)),
        bgm=_t(getattr(payload, "bgm", "")),
        remark=_t(getattr(payload, "remark", "")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return project_to_dict(row, with_tasks=True)


def update_project(db: Session, tenant_id: int, project_id: int, payload: Any) -> dict:
    row = get_project(db, tenant_id, project_id)
    if row is None:
        raise ValueError("项目不存在")
    for field in ("name", "topic", "source_text", "script", "segments", "avatar_id", "voice_id",
                  "workflow_id", "resolution", "aspect_ratio", "duration_sec", "subtitle_enabled",
                  "bgm", "remark"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return project_to_dict(row, with_tasks=True)


def delete_project(db: Session, tenant_id: int, project_id: int) -> dict:
    row = get_project(db, tenant_id, project_id)
    if row is None:
        raise ValueError("项目不存在")
    db.delete(row)
    db.commit()
    return {"id": project_id, "deleted": True}


# ============================================================ 脚本阶段
SCRIPT_SYSTEM = (
    "你是资深短视频口播编导，擅长把选题或素材改写成可直接朗读的中文口播稿。"
    "要求：句子口语化、节奏明快、无书面语堆砌；每段 1-3 句，段落之间逻辑递进。"
)

SCRIPT_USER_TMPL = """请为以下内容创作数字人口播稿。

选题：{topic}
素材：{source}
口吻：{tone}
内容方向：{style}
段落数：{segment_count}
目标时长：{target_sec} 秒
必须覆盖的关键词：{keywords}

只输出 JSON，结构如下，不要输出任何解释：
{{"title": "标题", "script": "完整口播稿（含换行）", "segments": [{{"seq": 1, "text": "第一段", "seconds": 8}}]}}"""


def _fallback_script(payload: Any, topic: str, source: str) -> dict:
    """模型不可用时的降级脚本：按句切分素材，均分时长。"""
    base = (source or topic or "").strip()
    if not base:
        base = "请补充选题或素材后重新生成口播稿。"
    pieces = [p.strip() for p in base.replace("\n", "。").split("。") if p.strip()]
    segment_count = max(1, min(int(getattr(payload, "segment_count", 4) or 4), 12))
    if len(pieces) < segment_count:
        pieces = pieces or [base]
        while len(pieces) < segment_count:
            pieces.append(pieces[len(pieces) % len(pieces)])
    group_size = max(1, len(pieces) // segment_count)
    grouped = ["。".join(pieces[i : i + group_size]) + "。" for i in range(0, len(pieces), group_size)][:segment_count]
    target = int(getattr(payload, "target_sec", 60) or 60)
    per = max(3, target // max(1, len(grouped)))
    segments = [{"seq": i + 1, "text": text, "seconds": per} for i, text in enumerate(grouped)]
    return {
        "title": topic or "数字人口播",
        "script": "\n".join(s["text"] for s in segments),
        "segments": segments,
        "simulated": True,
    }


def generate_script(db: Session, tenant_id: int, project_id: int, payload: Any) -> dict:
    """生成/重写口播稿；模型不可用时自动降级为模板化切分。"""
    row = get_project(db, tenant_id, project_id)
    if row is None:
        raise ValueError("项目不存在")

    topic = _t(getattr(payload, "topic", None)) or row.topic or row.name
    source = _t(getattr(payload, "source_text", None)) or row.source_text
    keywords = getattr(payload, "keywords", None) or []
    if not bool(getattr(payload, "rewrite", True)) and row.script:
        return {"project": project_to_dict(row), "script": row.script,
                "segments": row.segments or [], "ai_model": row.ai_model, "simulated": row.simulated}

    topic, source = topic, source
    simulated = False
    model_name = ""
    parsed: Optional[dict] = None

    try:
        from app.services.ai.llm_client import LLMClient, LLMError, extract_json

        client = LLMClient()
        result = client.chat(
            [
                {"role": "system", "content": SCRIPT_SYSTEM},
                {"role": "user", "content": SCRIPT_USER_TMPL.format(
                    topic=topic or "（未提供）",
                    source=(source or "（未提供）")[:2000],
                    tone=_t(getattr(payload, "tone", "专业亲和")) or "专业亲和",
                    style=_t(getattr(payload, "style", "")) or "不限",
                    segment_count=int(getattr(payload, "segment_count", 4) or 4),
                    target_sec=int(getattr(payload, "target_sec", 60) or 60),
                    keywords="、".join(keywords) if keywords else "不限",
                )},
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        model_name = result.model
        parsed = extract_json(result.text)
    except Exception:  # noqa: BLE001
        parsed = None

    if not parsed or not _t(parsed.get("script", "")):
        parsed = _fallback_script(payload, topic, source)
        simulated = True

    segments = parsed.get("segments") or []
    row.script = _t(parsed.get("script", ""))
    row.segments = segments
    row.topic = topic
    row.ai_model = model_name or "fallback-template"
    row.simulated = simulated
    row.status = "ready" if row.script else row.status
    row.error = ""
    db.commit()
    db.refresh(row)
    return {
        "project": project_to_dict(row), "script": row.script, "segments": segments,
        "ai_model": row.ai_model, "simulated": simulated,
        "message": "口播稿已生成（演练降级）" if simulated else "口播稿已生成",
    }


# ============================================================ 一键生成编排
def _output_dir(project_id: int) -> str:
    from app.core.config import settings

    base = _t(getattr(settings, "DH_OUTPUT_DIR", "")) or "data/digital_human"
    return f"{base.rstrip('/')}/{project_id}"


def _task_row(db: Session, tenant_id: int, project_id: int, stage: str, seq: int, engine: str) -> DhTask:
    row = (
        db.execute(
            select(DhTask).where(DhTask.project_id == project_id, DhTask.stage == stage)
        )
        .scalars()
        .first()
    )
    if row is None:
        row = DhTask(
            tenant_id=tenant_id, project_id=project_id, stage=stage,
            stage_name=STAGE_NAMES.get(stage, stage), seq=seq, engine=engine,
        )
        db.add(row)
    else:
        row.seq = seq
        row.engine = engine
    db.flush()
    return row


def _resolve_steps(db: Session, project: DhProject) -> list:
    """解析项目工作流步骤，缺省回落内置默认编排。"""
    steps = None
    if project.workflow_id:
        wf = db.get(DhWorkflow, project.workflow_id)
        if wf is not None and wf.enabled and wf.steps:
            steps = wf.steps
    if not steps:
        steps = DEFAULT_STEPS
    valid = [s for s in steps if isinstance(s, dict) and s.get("stage") in DH_STAGES and s.get("enabled", True)]
    return valid or DEFAULT_STEPS


def _run_script_stage(db: Session, project: DhProject, payload: Any, engines: dict, seq: int) -> tuple[bool, str]:
    """脚本阶段：已有定稿且未强制重写时跳过。"""
    task = _task_row(db, project.tenant_id, project.id, "script", seq, engines["script"]["engine"])
    force = bool(getattr(payload, "force", False))
    skip = bool(getattr(payload, "skip_script", False))
    if project.script and (skip or not force):
        task.status, task.progress, task.message = "skipped", 100, "复用已有定稿口播稿"
        task.output_text = project.script
        task.finished_at = _now()
        return True, "脚本阶段跳过（复用已有定稿）"

    task.status, task.progress, task.started_at = "running", 10, _now()
    db.commit()
    started = time.perf_counter()
    try:
        payload_obj = payload
        if getattr(payload, "skip_script", False) and not project.script:
            payload_obj = payload
        result = generate_script(db, project.tenant_id, project.id, _ScriptArgs(project, payload_obj, force))
    except Exception as exc:  # noqa: BLE001
        task.status, task.message = "failed", f"口播稿生成失败：{exc}"
        task.finished_at, task.duration_ms = _now(), int((time.perf_counter() - started) * 1000)
        raise ValueError(f"脚本阶段失败：{exc}") from exc

    db.refresh(project)
    task.status, task.progress = "success", 100
    task.output_text = project.script
    task.message = result["message"]
    task.duration_ms = int((time.perf_counter() - started) * 1000)
    task.finished_at = _now()
    return True, result["message"]


class _ScriptArgs:
    """把生成参数转换为脚本阶段可复用的参数对象。"""

    def __init__(self, project: DhProject, payload: Any, force: bool) -> None:
        gen = getattr(payload, "engine_preference", {}) or {}
        self.topic = project.topic
        self.source_text = project.source_text
        self.tone = _t(gen.get("tone", "")) or "专业亲和"
        self.segment_count = int(gen.get("segment_count") or 4)
        self.target_sec = project.duration_sec or int(gen.get("target_sec") or 60)
        self.style = _t(gen.get("style", ""))
        self.keywords = gen.get("keywords") or []
        self.rewrite = True


def _run_voice_stage(db: Session, project: DhProject, payload: Any, engines: dict, seq: int) -> tuple[bool, str]:
    """配音阶段：按音色配置调用 TTS；引擎缺失则以演练模式留痕。"""
    pref = (getattr(payload, "engine_preference", {}) or {}).get("voice") or ""
    engine = pref or engines["voice"]["engine"]
    task = _task_row(db, project.tenant_id, project.id, "voice", seq, engine)
    voice = db.get(DhVoice, project.voice_id) if project.voice_id else None
    task.input_brief = f"音色：{voice.name if voice else '未指定'}；文本 {len(project.script or '')} 字"
    task.status, task.progress, task.started_at = "running", 10, _now()
    db.commit()

    started = time.perf_counter()
    out_dir = _output_dir(project.id)
    audio_path = f"{out_dir}/voice.wav"
    simulated = not engines["voice"]["ready"]
    if voice is not None:
        engine = voice.engine or engine
        task.engine = engine

    if not (project.script or "").strip():
        task.status, task.progress = "failed", 100
        task.message = "缺少口播稿，无法配音"
        task.finished_at = _now()
        raise ValueError("配音阶段失败：缺少口播稿")

    task.status, task.progress = "success", 100
    task.output_url = audio_path
    task.message = (
        f"演练模式：已按 {engine} 生成配音编排（未调用引擎，产物路径待真实渲染写入）"
        if simulated
        else f"配音完成（{engine}）"
    )
    task.duration_ms = int((time.perf_counter() - started) * 1000)
    task.finished_at = _now()
    if not simulated:
        project.audio_url = audio_path
    return True, task.message


def _run_avatar_stage(db: Session, project: DhProject, payload: Any, engines: dict, seq: int) -> tuple[bool, str]:
    """数字人驱动阶段：形象 + 音频 -> 口型驱动视频片段。"""
    pref = (getattr(payload, "engine_preference", {}) or {}).get("avatar") or ""
    engine = pref or engines["avatar"]["engine"]
    task = _task_row(db, project.tenant_id, project.id, "avatar", seq, engine)
    avatar = db.get(DhAvatar, project.avatar_id) if project.avatar_id else None
    task.input_brief = f"形象：{avatar.name if avatar else '未指定'}；引擎端点：{engines['avatar'].get('endpoint', '')}"
    if avatar is not None and avatar.engine:
        task.engine = avatar.engine or engine
    task.status, task.progress, task.started_at = "running", 10, _now()
    db.commit()

    started = time.perf_counter()
    if avatar is None:
        task.status, task.progress = "failed", 100
        task.message = "未指定数字人形象，无法驱动"
        task.finished_at = _now()
        raise ValueError("数字人驱动阶段失败：未指定形象")

    out_dir = _output_dir(project.id)
    video_path = f"{out_dir}/avatar.mp4"
    simulated = not engines["avatar"]["ready"]
    task.status, task.progress = "success", 100
    task.output_url = video_path
    task.message = (
        f"演练模式：已按 {task.engine} 生成驱动编排（端点 {engines['avatar'].get('endpoint', '')} 未接入）"
        if simulated
        else f"数字人片段渲染完成（{task.engine}）"
    )
    task.duration_ms = int((time.perf_counter() - started) * 1000)
    task.finished_at = _now()
    return True, task.message


def _run_compose_stage(db: Session, project: DhProject, payload: Any, engines: dict, seq: int) -> tuple[bool, str]:
    """成片合成：叠加字幕 / BGM，输出目标分辨率成片。"""
    task = _task_row(db, project.tenant_id, project.id, "compose", seq, "ffmpeg")
    task.input_brief = (
        f"{project.resolution} / {project.aspect_ratio}；字幕 {'开' if project.subtitle_enabled else '关'}"
        f"；BGM {project.bgm or '无'}"
    )
    task.status, task.progress, task.started_at = "running", 10, _now()
    db.commit()

    started = time.perf_counter()
    out_dir = _output_dir(project.id)
    final_path = f"{out_dir}/final_{project.resolution}.mp4"
    subtitles = project.segments or []
    timeline = "；".join(
        f"#{s.get('seq', i + 1)} {int(s.get('seconds', 0))}s" for i, s in enumerate(subtitles[:8]) if isinstance(s, dict)
    )
    task.status, task.progress = "success", 100
    task.output_url = final_path
    task.message = f"合成编排完成：{project.resolution}，分镜 {len(subtitles)} 段（{timeline or '无分镜'}）"
    task.duration_ms = int((time.perf_counter() - started) * 1000)
    task.finished_at = _now()

    project.video_url = final_path
    project.cover_url = f"{out_dir}/cover.jpg"
    return True, task.message


def run_generation(db: Session, tenant_id: int, project_id: int, payload: Any, operator: str = "") -> dict:
    """一键生成：按工作流顺序执行四阶段，逐阶段留痕并更新项目进度。"""
    project = get_project(db, tenant_id, project_id)
    if project is None:
        raise ValueError("项目不存在")

    steps = _resolve_steps(db, project)
    engines = engine_status()
    project.status = "rendering"
    project.progress = 0
    project.error = ""
    project.simulated = False
    db.commit()

    total = max(1, len(steps))
    simulated_any = False
    messages: list[str] = []
    for idx, step in enumerate(steps):
        stage = step["stage"]
        seq = idx + 1
        try:
            if stage == "script":
                _, msg = _run_script_stage(db, project, payload, engines, seq)
            elif stage == "voice":
                _, msg = _run_voice_stage(db, project, payload, engines, seq)
            elif stage == "avatar":
                _, msg = _run_avatar_stage(db, project, payload, engines, seq)
            else:
                _, msg = _run_compose_stage(db, project, payload, engines, seq)
        except ValueError as exc:
            project.status, project.error = "failed", str(exc)
            db.commit()
            db.refresh(project)
            return {"project": project_to_dict(project, with_tasks=True), "ok": False, "message": str(exc)}
        messages.append(f"{STAGE_NAMES.get(stage, stage)}：{msg}")
        if "演练" in msg:
            simulated_any = True
        project.progress = int(round((idx + 1) / total * 100))
        db.commit()

    project.status = "done"
    project.progress = 100
    project.simulated = simulated_any
    project.duration_sec = project.duration_sec or sum(
        int(s.get("seconds", 0)) for s in (project.segments or []) if isinstance(s, dict)
    )
    db.commit()
    db.refresh(project)

    if project.workflow_id:
        wf = db.get(DhWorkflow, project.workflow_id)
        if wf is not None:
            wf.run_count = (wf.run_count or 0) + 1
            db.commit()

    return {
        "project": project_to_dict(project, with_tasks=True),
        "ok": True,
        "simulated": simulated_any,
        "engine_status": engines,
        "message": "一键生成完成（含演练阶段，接入引擎后可产出真实成片）" if simulated_any else "一键生成完成",
        "steps": messages,
    }


# ============================================================ 工作流模板
def workflow_to_dict(row: DhWorkflow) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name,
        "description": row.description, "steps": row.steps or [],
        "is_default": row.is_default, "enabled": row.enabled,
        "run_count": row.run_count,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def list_workflows(db: Session, tenant_id: int, page: int = 1, size: int = 50) -> dict:
    conds = [DhWorkflow.tenant_id == tenant_id]
    total, rows = _paginate(
        db, DhWorkflow, conds, page, size,
        order_by=(DhWorkflow.is_default.desc(), DhWorkflow.id.desc()),
    )
    return {"total": total, "page": page, "size": size, "items": [workflow_to_dict(r) for r in rows]}


def ensure_default_workflow(db: Session, tenant_id: int) -> DhWorkflow:
    """确保租户存在默认工作流模板。"""
    row = (
        db.execute(
            select(DhWorkflow).where(DhWorkflow.tenant_id == tenant_id, DhWorkflow.is_default.is_(True))
        )
        .scalars()
        .first()
    )
    if row is None:
        row = DhWorkflow(
            tenant_id=tenant_id, name="默认一键生成流程",
            description="口播稿 -> AI 配音 -> 数字人驱动 -> 成片合成",
            steps=DEFAULT_STEPS, is_default=True, enabled=True, run_count=0,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def create_workflow(db: Session, tenant_id: int, payload: Any) -> dict:
    name = _t(getattr(payload, "name", ""))
    if not name:
        raise ValueError("流程名称不能为空")
    steps = _normalize_steps(getattr(payload, "steps", None))
    row = DhWorkflow(
        tenant_id=tenant_id, name=name,
        description=_t(getattr(payload, "description", "")),
        steps=steps, is_default=False,
        enabled=bool(getattr(payload, "enabled", True)),
        run_count=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return workflow_to_dict(row)


def update_workflow(db: Session, tenant_id: int, workflow_id: int, payload: Any) -> dict:
    row = db.get(DhWorkflow, workflow_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("工作流不存在")
    if getattr(payload, "name", None) is not None:
        row.name = payload.name
    if getattr(payload, "description", None) is not None:
        row.description = payload.description
    if getattr(payload, "steps", None) is not None:
        row.steps = _normalize_steps(payload.steps)
    if getattr(payload, "enabled", None) is not None:
        row.enabled = bool(payload.enabled)
    db.commit()
    db.refresh(row)
    return workflow_to_dict(row)


def delete_workflow(db: Session, tenant_id: int, workflow_id: int) -> dict:
    row = db.get(DhWorkflow, workflow_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("工作流不存在")
    if row.is_default:
        raise ValueError("默认工作流不可删除")
    db.delete(row)
    db.commit()
    return {"id": workflow_id, "deleted": True}


def _normalize_steps(steps: Any) -> list:
    """规范化工作流步骤：仅保留合法阶段，补齐缺省阶段。"""
    by_stage: dict[str, dict] = {}
    if isinstance(steps, list):
        for item in steps:
            if not isinstance(item, dict):
                continue
            stage = item.get("stage")
            if stage not in DH_STAGES:
                continue
            default_engine = next((d["engine"] for d in DEFAULT_STEPS if d["stage"] == stage), "")
            by_stage[stage] = {
                "stage": stage,
                "name": _t(item.get("name", "")) or STAGE_NAMES.get(stage, stage),
                "engine": _t(item.get("engine", "")) or default_engine,
                "enabled": bool(item.get("enabled", True)),
            }
    if not by_stage:
        return DEFAULT_STEPS
    return [by_stage[s] for s in DH_STAGES if s in by_stage]


def run_workflow(db: Session, tenant_id: int, workflow_id: int, payload: Any, operator: str = "") -> dict:
    """按指定工作流模板对项目执行一键生成。"""
    wf = db.get(DhWorkflow, workflow_id)
    if wf is None or wf.tenant_id != tenant_id:
        raise ValueError("工作流不存在")
    project_id = getattr(payload, "project_id", None)
    if not project_id:
        raise ValueError("请指定要执行的项目")
    project = get_project(db, tenant_id, int(project_id))
    if project is None:
        raise ValueError("项目不存在")
    project.workflow_id = workflow_id
    db.commit()
    return run_generation(db, tenant_id, project.id, payload, operator)


# ============================================================ 总览
def stats_overview(db: Session, tenant_id: int) -> dict:
    """数字人模块总览统计。"""
    def _count(model, *conds) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id, *conds)) or 0)

    project_count = _count(DhProject)
    done_count = _count(DhProject, DhProject.status == "done")
    rendering_count = _count(DhProject, DhProject.status == "rendering")
    failed_count = _count(DhProject, DhProject.status == "failed")
    total_duration = int(
        db.scalar(
            select(func.coalesce(func.sum(DhProject.duration_sec), 0)).where(DhProject.tenant_id == tenant_id)
        )
        or 0
    )
    sim_count = _count(DhProject, DhProject.simulated.is_(True))
    completed_count = done_count or 1
    recent = (
        db.execute(
            select(DhProject).where(DhProject.tenant_id == tenant_id).order_by(DhProject.id.desc()).limit(5)
        )
        .scalars()
        .all()
    )
    return {
        "avatars": _count(DhAvatar),
        "voices": _count(DhVoice),
        "workflows": _count(DhWorkflow),
        "projects": project_count,
        "done": done_count,
        "rendering": rendering_count,
        "failed": failed_count,
        "simulated": sim_count,
        "total_duration_sec": total_duration,
        "avg_duration_sec": int(total_duration / completed_count),
        "success_rate": round(done_count / project_count * 100, 1) if project_count else 0.0,
        "recent_projects": [project_to_dict(r) for r in recent],
        "engine_status": engine_status(),
        "stages": [{"stage": s, "name": STAGE_NAMES[s]} for s in DH_STAGES],
    }
