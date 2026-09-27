"""P9 硬件探测服务：CPU / 内存 / GPU 与显存 / 磁盘 / 网络出口。

设计要点：
- 零新增第三方依赖：仅用标准库 + 系统自带命令（nvidia-smi / PowerShell-WMI / wmic / procfs）。
- 分层探测：优先读取「宿主机快照」（deploy/scripts/probe_host_hardware.ps1 在 Windows 宿主机生成，
  写入 <root>/data/hardware/host_hardware.json，经 ./data 卷挂载进容器），再退化为容器内本地探测。
- 优雅降级：任一子项失败只追加到 degradations（含失败原因与修复建议），不抛异常、不影响其它子项。
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import string
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import BASE_DIR, settings

HOST_SNAPSHOT_RELATIVE = Path("hardware") / "host_hardware.json"
_IS_WINDOWS = os.name == "nt"

# 各探测子项的修复建议（写入 degradations.suggestion，供前端直接展示）
_SUGGESTIONS: dict[str, str] = {
    "host_snapshot": (
        "在 Windows 宿主机执行 deploy/scripts/probe_host_hardware.ps1 生成快照"
        "（默认输出 <root>/data/hardware/host_hardware.json），容器内即可读到真实 CPU/GPU/磁盘数据"
    ),
    "cpu": "Windows 宿主机需可执行 powershell（WMI）；Linux 需可读 /proc/cpuinfo",
    "memory": "Windows 需可执行 powershell（WMI）；Linux 需可读 /proc/meminfo",
    "disk": "确认挂载卷当前用户可访问；容器内无法枚举宿主机全部磁盘时可用宿主机快照补齐",
    "gpu": (
        "宿主机安装 NVIDIA 驱动并生成宿主机快照；容器内直读 nvidia-smi 需以 --gpus all 启动，"
        "Windows 的 WMI AdapterRAM 存在 4GB 上限，不建议作为唯一依据"
    ),
    "network": "出口探测只做只读连通性检查，失败不影响模型接入；如需禁用可置 HARDWARE_NETWORK_PROBE_ENABLED=false",
    "wmi": "确认宿主机 PowerShell 可用（Get-CimInstance 需要 Windows PowerShell 5.1 及以上）",
}


# ------------------------------------------------------------------ 基础工具
def data_dir() -> Path:
    """受管数据目录（宿主机 <root>/data；容器内为同一目录的挂载点）。"""
    raw = Path(settings.DATA_DIR)
    return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()


def host_snapshot_path() -> Path:
    """宿主机硬件快照文件路径。"""
    return data_dir() / HOST_SNAPSHOT_RELATIVE


def _iso(value: Optional[datetime] = None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _run(cmd: list[str], timeout: Optional[int] = None) -> tuple[bool, str, str]:
    """执行系统命令，返回 (ok, stdout, error)；异常与超时一律不抛出。"""
    limit = timeout or settings.HARDWARE_PROBE_TIMEOUT_SECONDS
    kwargs: dict[str, Any] = {}
    if _IS_WINDOWS:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW，不弹控制台窗口
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=limit, **kwargs)
    except FileNotFoundError:
        return False, "", f"命令不存在：{cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "", f"命令超时（>{limit}s）：{cmd[0]}"
    except Exception as exc:  # noqa: BLE001
        return False, "", f"命令执行失败：{cmd[0]} - {exc}"

    out = proc.stdout.decode("utf-8", "ignore") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
    err = proc.stderr.decode("utf-8", "ignore") if isinstance(proc.stderr, bytes) else (proc.stderr or "")
    if proc.returncode != 0:
        return False, out, (err.strip() or f"退出码 {proc.returncode}")
    return True, out, err


def _powershell_json(command: str, timeout: Optional[int] = None) -> tuple[bool, Any, str]:
    """执行 PowerShell 并把输出解析为 JSON（ConvertTo-Json 结果）。"""
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return False, None, "未找到 powershell / pwsh 可执行文件"
    ok, out, err = _run([exe, "-NoProfile", "-NonInteractive", "-Command", command], timeout)
    if not ok:
        return False, None, err
    text = out.strip()
    if not text:
        return False, None, "命令无输出"
    try:
        return True, json.loads(text), ""
    except json.JSONDecodeError as exc:
        return False, None, f"输出非合法 JSON：{exc}"


def _as_rows(value: Any) -> list[dict]:
    """把 ConvertTo-Json 的单对象/数组统一成列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ 环境
def detect_environment() -> dict:
    """运行环境识别：容器 / 宿主机、操作系统、Python 版本。"""
    is_container = Path("/.dockerenv").exists()
    if not is_container:
        try:
            is_container = "docker" in Path("/proc/1/cgroup").read_text(errors="ignore")
        except OSError:
            is_container = False
    return {
        "host_name": platform.node(),
        "platform": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "is_container": is_container,
        "is_windows": _IS_WINDOWS,
    }


# ------------------------------------------------------------------ CPU
def probe_cpu() -> dict:
    """CPU 型号 / 物理核 / 逻辑核 / 主频。"""
    info: dict[str, Any] = {
        "model": None,
        "physical_cores": None,
        "logical_cores": os.cpu_count(),
        "freq_mhz": None,
        "socket_count": None,
        "source": None,
        "warnings": [],
    }
    if _IS_WINDOWS:
        ok, data, err = _powershell_json(
            "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
            "NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress"
        )
        rows = _as_rows(data)
        if ok and rows:
            row = rows[0]
            info.update(
                {
                    "model": str(row.get("Name") or "").strip() or None,
                    "physical_cores": _int(row.get("NumberOfCores")),
                    "logical_cores": _int(row.get("NumberOfLogicalProcessors")) or info["logical_cores"],
                    "freq_mhz": _int(row.get("MaxClockSpeed")),
                    "socket_count": len(rows),
                    "source": "wmi:Win32_Processor",
                }
            )
        else:
            info["warnings"].append(f"WMI 读取 CPU 失败：{err}")
    else:
        try:
            text = Path("/proc/cpuinfo").read_text(errors="ignore")
            model: Optional[str] = None
            freq: Optional[int] = None
            cores: Optional[int] = None
            logical = 0
            for line in text.splitlines():
                if line.startswith("processor"):
                    logical += 1
                elif line.startswith("model name") and model is None:
                    model = line.split(":", 1)[1].strip()
                elif line.startswith("cpu MHz") and freq is None:
                    freq = _int(line.split(":", 1)[1].strip())
                elif line.startswith("cpu cores") and cores is None:
                    cores = _int(line.split(":", 1)[1].strip())
            if model or logical:
                info.update(
                    {
                        "model": model,
                        "physical_cores": cores,
                        "logical_cores": logical or info["logical_cores"],
                        "freq_mhz": freq,
                        "source": "procfs:/proc/cpuinfo",
                    }
                )
        except OSError as exc:
            info["warnings"].append(f"读取 /proc/cpuinfo 失败：{exc}")

    if not info["model"]:
        info["model"] = platform.processor() or platform.machine() or None
        info["source"] = info["source"] or "platform"
    return info


# ------------------------------------------------------------------ 内存
def probe_memory() -> dict:
    """内存总量 / 可用量 / 使用率。"""
    info: dict[str, Any] = {
        "total_mb": None,
        "available_mb": None,
        "used_percent": None,
        "source": None,
        "warnings": [],
    }
    if _IS_WINDOWS:
        ok, data, err = _powershell_json(
            "Get-CimInstance Win32_OperatingSystem | "
            "Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress"
        )
        rows = _as_rows(data)
        if ok and rows:
            row = rows[0]
            total_kb = _int(row.get("TotalVisibleMemorySize"))
            free_kb = _int(row.get("FreePhysicalMemory"))
            if total_kb:
                info.update(
                    {
                        "total_mb": round(total_kb / 1024),
                        "available_mb": round(free_kb / 1024) if free_kb else None,
                        "source": "wmi:Win32_OperatingSystem",
                    }
                )
            else:
                info["warnings"].append("WMI 未返回内存容量（TotalVisibleMemorySize 为空）")
        else:
            info["warnings"].append(f"WMI 读取内存失败：{err}")
    else:
        try:
            text = Path("/proc/meminfo").read_text(errors="ignore")
            total_kb: Optional[int] = None
            avail_kb: Optional[int] = None
            for line in text.splitlines():
                parts = line.split()
                if line.startswith("MemTotal:") and len(parts) >= 2:
                    total_kb = _int(parts[1])
                elif line.startswith("MemAvailable:") and len(parts) >= 2:
                    avail_kb = _int(parts[1])
            if total_kb:
                info.update(
                    {
                        "total_mb": round(total_kb / 1024),
                        "available_mb": round(avail_kb / 1024) if avail_kb else None,
                        "source": "procfs:/proc/meminfo",
                    }
                )
        except OSError as exc:
            info["warnings"].append(f"读取 /proc/meminfo 失败：{exc}")

    if info["total_mb"] is None:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            info.update(
                {
                    "total_mb": round(pages * page_size / 1048576),
                    "source": "os.sysconf",
                }
            )
        except (ValueError, OSError, AttributeError) as exc:
            info["warnings"].append(f"os.sysconf 读取内存失败：{exc}")

    if info["total_mb"] and info["available_mb"]:
        info["used_percent"] = round((1 - info["available_mb"] / info["total_mb"]) * 100, 1)
    return info


# ------------------------------------------------------------------ 磁盘
def probe_disks() -> dict:
    """磁盘挂载点容量（容器内自动去重同卷挂载）。"""
    result: dict[str, Any] = {"disks": [], "source": "shutil.disk_usage", "warnings": []}
    if _IS_WINDOWS:
        roots = [f"{letter}:\\" for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
    else:
        roots = ["/"]
        if Path("/app/data").exists():
            roots.append("/app/data")

    seen: set[tuple[int, int]] = set()
    for root in roots:
        try:
            usage = shutil.disk_usage(root)
        except OSError as exc:
            result["warnings"].append(f"读取磁盘 {root} 失败：{exc}")
            continue
        if usage.total <= 0:
            continue
        key = (usage.total, usage.free)
        if key in seen:
            continue  # 同一物理卷（如容器内 / 与 /app/data）只保留一次
        seen.add(key)
        result["disks"].append(
            {
                "mount": root,
                "total_gb": round(usage.total / 1024**3, 1),
                "free_gb": round(usage.free / 1024**3, 1),
                "used_percent": round(usage.used / usage.total * 100, 1),
            }
        )
    if not result["disks"]:
        result["warnings"].append("未获取到任何磁盘容量信息")
    return result


# ------------------------------------------------------------------ GPU
def _gpu_from_nvidia_smi() -> tuple[list[dict], str]:
    """优先用 nvidia-smi 读取真实显存。"""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return [], "容器内未找到 nvidia-smi（未挂载 GPU 或宿主机未安装 NVIDIA 驱动）"
    ok, out, err = _run(
        [
            exe,
            "--query-gpu=index,name,memory.total,memory.used,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not ok:
        return [], f"nvidia-smi 执行失败：{err}"
    gpus: list[dict] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        gpus.append(
            {
                "index": _int(parts[0]) or 0,
                "name": parts[1],
                "vram_total_mb": _int(parts[2]),
                "vram_used_mb": _int(parts[3]),
                "driver": parts[4] if len(parts) > 4 else None,
                "vendor": "NVIDIA",
                "source": "nvidia-smi",
                "vram_accurate": True,
            }
        )
    if not gpus:
        return [], "nvidia-smi 无输出（可能不存在可用 GPU）"
    return gpus, ""


_PS_GPU_LIST = (
    "Get-CimInstance Win32_VideoController | "
    "Select-Object Name,AdapterRAM,DriverVersion,AdapterCompatibility | ConvertTo-Json -Compress"
)

# WMI AdapterRAM 有 4GB 上限，显存改从显示驱动注册表读 qwMemorySize
_PS_GPU_VRAM = (
    "$base='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
    "{4d36e968-e325-11ce-bfc1-08002be10318}';"
    "$out=@();"
    "Get-ChildItem $base -ErrorAction SilentlyContinue | ForEach-Object {"
    " $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue;"
    " $v = $p.'HardwareInformation.qwMemorySize';"
    " if ($v) { $out += [PSCustomObject]@{ Slot=$_.PSChildName; Desc=$p.DriverDesc; Vram=[int64]$v } } };"
    "$out | ConvertTo-Json -Compress"
)


def _gpu_from_windows() -> tuple[list[dict], list[str]]:
    """Windows 宿主机：WMI 兜底 + 注册表补齐显存。"""
    warnings: list[str] = []
    ok, data, err = _powershell_json(_PS_GPU_LIST)
    rows = _as_rows(data) if ok else []
    if not ok:
        warnings.append(f"WMI 读取显卡失败：{err}")

    vram_map: list[dict] = []
    ok_v, data_v, err_v = _powershell_json(_PS_GPU_VRAM)
    if ok_v:
        vram_map = _as_rows(data_v)
    elif err_v:
        warnings.append(f"注册表读取显存失败：{err_v}")

    gpus: list[dict] = []
    for idx, row in enumerate(rows):
        name = str(row.get("Name") or "").strip()
        adapter_ram = _int(row.get("AdapterRAM"))
        vram_mb: Optional[int] = None
        accurate = False
        for item in vram_map:
            desc = str(item.get("Desc") or "")
            if desc and (desc.lower() in name.lower() or name.lower() in desc.lower()):
                raw_bytes = _int(item.get("Vram"))
                if raw_bytes:
                    vram_mb = round(raw_bytes / 1048576)
                    accurate = True
                    break
        if vram_mb is None and adapter_ram:
            vram_mb = round(adapter_ram / 1048576)
            accurate = False  # AdapterRAM 存在 4GB 上限，仅供参考
        gpus.append(
            {
                "index": idx,
                "name": name or (f"GPU {idx}" if rows else "未知显卡"),
                "vram_total_mb": vram_mb,
                "vram_used_mb": None,
                "driver": str(row.get("DriverVersion") or "").strip() or None,
                "vendor": str(row.get("AdapterCompatibility") or "").strip() or None,
                "source": "wmi:Win32_VideoController",
                "vram_accurate": accurate,
            }
        )
    if gpus and not any(g["vram_accurate"] for g in gpus):
        warnings.append(
            "显存数值来自 WMI AdapterRAM（存在 4GB 上限，可能偏低），"
            "精确值请以宿主机 nvidia-smi 或驱动注册表 qwMemorySize 为准"
        )
    return gpus, warnings


_VENDOR_MAP = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel", "0x1af4": "Virtio"}


def _gpu_from_linux_sysfs() -> tuple[list[dict], list[str]]:
    """Linux（含容器）：从 /sys/class/drm 读取显卡信息，显存多数场景不可读。"""
    warnings: list[str] = []
    gpus: list[dict] = []
    base = Path("/sys/class/drm")
    if not base.exists():
        return [], ["未找到 /sys/class/drm，无法读取显卡信息"]
    for card in sorted(base.glob("card[0-9]*")):
        if "-" in card.name:  # card0-DP-1 之类的连接器目录
            continue
        device = card / "device"
        vendor_id = None
        vram_mb: Optional[int] = None
        try:
            vendor_id = (device / "vendor").read_text(errors="ignore").strip().lower()
        except OSError:
            vendor_id = None
        for candidate in ("mem_info_vram_total", "mem_info_gtt_total"):
            try:
                raw = _int((device / candidate).read_text(errors="ignore").strip())
            except OSError:
                raw = None
            if raw:
                vram_mb = round(raw / 1048576)
                break
        gpus.append(
            {
                "index": _int(card.name.replace("card", "")) or len(gpus),
                "name": f"{_VENDOR_MAP.get(vendor_id or '', '未知厂商')} GPU（{card.name}）",
                "vram_total_mb": vram_mb,
                "vram_used_mb": None,
                "driver": None,
                "vendor": _VENDOR_MAP.get(vendor_id or "", None),
                "source": "sysfs:/sys/class/drm",
                "vram_accurate": bool(vram_mb),
            }
        )
    if gpus and not any(g["vram_accurate"] for g in gpus):
        warnings.append("容器内无法读取显存容量（sysfs 未暴露），建议用宿主机快照补齐")
    return gpus, warnings


def probe_gpu() -> dict:
    """GPU 列表 + 总显存（nvidia-smi → WMI/注册表 → sysfs 逐级降级）。"""
    result: dict[str, Any] = {"gpus": [], "sources": [], "warnings": [], "vram_total_mb": None, "vram_accurate": False}

    gpus, err = _gpu_from_nvidia_smi()
    if gpus:
        result["gpus"] = gpus
        result["sources"].append("nvidia-smi")
    elif err:
        result["warnings"].append(err)

    if not result["gpus"] and _IS_WINDOWS:
        gpus, warnings = _gpu_from_windows()
        if gpus:
            result["gpus"] = gpus
            result["sources"].append("wmi:Win32_VideoController")
        result["warnings"].extend(warnings)

    if not result["gpus"] and not _IS_WINDOWS:
        gpus, warnings = _gpu_from_linux_sysfs()
        if gpus:
            result["gpus"] = gpus
            result["sources"].append("sysfs:/sys/class/drm")
        result["warnings"].extend(warnings)

    if not result["gpus"]:
        result["warnings"].append("未探测到 GPU（如为容器运行，需 --gpus all 并安装宿主机驱动；无独显可走 CPU 推理或云端端点）")

    vram_total = sum(g.get("vram_total_mb") or 0 for g in result["gpus"])
    result["vram_total_mb"] = vram_total or None
    result["vram_accurate"] = bool(result["gpus"]) and all(
        g.get("vram_accurate", False) for g in result["gpus"]
    )
    result["vendors"] = sorted({str(g.get("vendor") or "unknown") for g in result["gpus"]})
    return result


# ------------------------------------------------------------------ 网络
def _probe_url(label: str, url: str, timeout: float = 4.0) -> dict:
    """按 URL 的 host:port 做 TCP 可达性探测（不发送业务请求）。"""
    from urllib.parse import urlparse

    parsed = urlparse(url or "")
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    item: dict[str, Any] = {
        "label": label,
        "url": url,
        "host": host,
        "port": port,
        "reachable": False,
        "latency_ms": None,
        "message": "",
    }
    if not host:
        item["message"] = "地址无效"
        return item
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            item["reachable"] = True
            item["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
            item["message"] = "TCP 可达"
    except OSError as exc:
        item["message"] = f"TCP 不可达：{exc}"
    return item


def probe_network() -> dict:
    """网卡概况 + DNS / TCP 出口 / 出口 IP + 关键端点可达性。"""
    info: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "interfaces": [],
        "egress_ip": None,
        "dns_ok": None,
        "tcp_ok": None,
        "latency_ms": None,
        "targets": [],
        "sources": [],
        "warnings": [],
    }

    if _IS_WINDOWS:
        ok, data, err = _powershell_json(
            "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed | ConvertTo-Json -Compress"
        )
        if ok:
            info["sources"].append("Get-NetAdapter")
            for row in _as_rows(data):
                info["interfaces"].append(
                    {
                        "name": row.get("Name"),
                        "desc": row.get("InterfaceDescription"),
                        "status": row.get("Status"),
                        "speed": row.get("LinkSpeed"),
                    }
                )
        elif err:
            info["warnings"].append(f"读取网卡失败：{err}")
    else:
        try:
            for nic in sorted(Path("/sys/class/net").iterdir()):
                if nic.name == "lo":
                    continue
                try:
                    state = (nic / "operstate").read_text(errors="ignore").strip()
                except OSError:
                    state = None
                info["interfaces"].append({"name": nic.name, "desc": None, "status": state, "speed": None})
            info["sources"].append("sysfs:/sys/class/net")
        except OSError as exc:
            info["warnings"].append(f"读取网卡失败：{exc}")

    if not settings.HARDWARE_NETWORK_PROBE_ENABLED:
        info["warnings"].append("网络出口探测已关闭（HARDWARE_NETWORK_PROBE_ENABLED=false）")
        return info

    started = time.perf_counter()
    try:
        socket.gethostbyname("www.baidu.com")
        info["dns_ok"] = True
    except OSError as exc:
        info["dns_ok"] = False
        info["warnings"].append(f"DNS 解析失败：{exc}")

    try:
        with socket.create_connection(("223.5.5.5", 53), timeout=3):
            info["tcp_ok"] = True
    except OSError as exc:
        info["tcp_ok"] = False
        info["warnings"].append(f"TCP 出口探测失败（223.5.5.5:53）：{exc}")
    info["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    info["sources"].append("socket:dns+tcp")

    # 出口公网 IP（失败不影响其它探测）
    try:
        import httpx

        kwargs: dict[str, Any] = {"timeout": 5.0}
        if settings.AI_PROXY:
            kwargs["proxy"] = settings.AI_PROXY
        resp = httpx.get("https://api.ipify.org?format=json", **kwargs)
        if resp.status_code == 200:
            info["egress_ip"] = (resp.json() or {}).get("ip")
            info["sources"].append("https:api.ipify.org")
        else:
            info["warnings"].append(f"出口 IP 查询返回 HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        info["warnings"].append(f"出口 IP 查询失败：{exc}")

    info["targets"] = [
        _probe_url("本地 Ollama", settings.AI_LOCAL_BASE_URL),
        _probe_url("云端兼容端点", settings.AI_API_BASE_URL),
    ]
    return info


# ------------------------------------------------------------------ 宿主机快照
def load_host_snapshot(max_age_hours: Optional[int] = None) -> tuple[Optional[dict], Optional[str]]:
    """读取宿主机快照，返回 (数据, 失效/缺失原因)。"""
    path = host_snapshot_path()
    if not path.exists():
        return None, f"未找到宿主机快照 {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"宿主机快照解析失败：{exc}"
    if not isinstance(data, dict):
        return None, "宿主机快照格式异常（非 JSON 对象）"

    limit = settings.HARDWARE_HOST_SNAPSHOT_MAX_AGE_HOURS if max_age_hours is None else max_age_hours
    stamp = data.get("probed_at")
    if stamp and limit > 0:
        try:
            probed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if probed.tzinfo is None:
                probed = probed.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - probed
            if age > timedelta(hours=limit):
                data["stale"] = True
                data["stale_reason"] = f"宿主机快照已过期（{age.days} 天前生成，阈值 {limit} 小时）"
        except ValueError:
            data["stale"] = False
    return data, None


# ------------------------------------------------------------------ 主入口
def probe(include_host: bool = True) -> dict:
    """执行一次完整硬件探测（任何子项失败都会降级而非中断）。"""
    started = time.perf_counter()
    degradations: list[dict] = []
    sources: list[str] = []

    host: Optional[dict] = None
    if include_host:
        host, host_reason = load_host_snapshot()
        if host_reason:
            degradations.append(
                {
                    "item": "host_snapshot",
                    "reason": host_reason,
                    "suggestion": _SUGGESTIONS["host_snapshot"],
                }
            )
        elif host and host.get("stale"):
            degradations.append(
                {
                    "item": "host_snapshot",
                    "reason": host.get("stale_reason") or "宿主机快照已过期",
                    "suggestion": "重新执行 deploy/scripts/probe_host_hardware.ps1 刷新快照",
                }
            )

    cpu = probe_cpu()
    memory = probe_memory()
    disk = probe_disks()
    gpu = probe_gpu()
    network = probe_network()

    # 容器内探测不到的项，用宿主机快照补齐（Windows 宿主机数据更真实）
    if host:
        if not gpu["gpus"] and (host.get("gpus") or []):
            host_gpus = [{**g, "source": g.get("source") or "host-snapshot"} for g in host["gpus"]]
            vram_total = sum(g.get("vram_total_mb") or 0 for g in host_gpus)
            gpu = {
                "gpus": host_gpus,
                "sources": ["host-snapshot"],
                "warnings": [],
                "vram_total_mb": vram_total or None,
                "vram_accurate": all(g.get("vram_accurate", False) for g in host_gpus),
                "vendors": sorted({str(g.get("vendor") or "unknown") for g in host_gpus}),
            }
            sources.append("gpu:host-snapshot")
        if not memory.get("total_mb") and (host.get("memory") or {}).get("total_mb"):
            memory = {**host["memory"], "source": "host-snapshot", "warnings": memory.get("warnings", [])}
            sources.append("memory:host-snapshot")
        if cpu.get("physical_cores") is None and (host.get("cpu") or {}).get("physical_cores"):
            cpu = {**host["cpu"], "source": "host-snapshot", "warnings": cpu.get("warnings", [])}
            sources.append("cpu:host-snapshot")
        if not disk["disks"] and (host.get("disks") or []):
            disk = {
                "disks": [{**d, "source": "host-snapshot"} for d in host["disks"]],
                "source": "host-snapshot",
                "warnings": [],
            }
            sources.append("disk:host-snapshot")
        if not network.get("egress_ip") and (host.get("network") or {}).get("egress_ip"):
            network = {
                **host["network"],
                "sources": ["host-snapshot"],
                "warnings": network.get("warnings", []),
            }
            sources.append("network:host-snapshot")

    for item, section in (("cpu", cpu), ("memory", memory), ("disk", disk), ("gpu", gpu), ("network", network)):
        for message in section.get("warnings") or []:
            degradations.append(
                {
                    "item": item,
                    "reason": message,
                    "suggestion": _SUGGESTIONS.get(item, ""),
                }
            )
        if section.get("source"):
            sources.append(f"{item}:{section['source']}")

    return {
        "probed_at": _iso(),
        "environment": detect_environment(),
        "cpu": cpu,
        "memory": memory,
        "disks": disk["disks"],
        "disk_source": disk.get("source"),
        "gpus": gpu["gpus"],
        "gpu_vram": {
            "total_mb": gpu.get("vram_total_mb"),
            "total_gb": round((gpu.get("vram_total_mb") or 0) / 1024, 1) if gpu.get("vram_total_mb") else None,
            "accurate": gpu.get("vram_accurate"),
            "vendors": gpu.get("vendors") or [],
        },
        "network": network,
        "degradations": degradations,
        "sources": sources,
        "host_snapshot": {
            "available": bool(host),
            "path": str(host_snapshot_path()),
            "probed_at": (host or {}).get("probed_at"),
            "stale": bool((host or {}).get("stale")),
            "platform": ((host or {}).get("environment") or {}).get("platform"),
        },
        "probe_ms": round((time.perf_counter() - started) * 1000, 1),
    }
