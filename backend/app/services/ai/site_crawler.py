"""站内预览与可控抓取（P3 内置浏览器）。

在受控前提下抓取站点自身页面，用于站内预览与 SEO/GEO 体检：

- 仅允许 http/https，且目标 host 必须与站点配置的 host 一致（同域），避免被当作通用抓取代理；
- 拒绝云元数据与内网 / 保留地址（本机回环放行，用于自托管站点的本地预览）；
- 单次读取上限 512KB、超时 10s，不自动跟随重定向（跨域跳转会绕过同域约束）。
"""
from __future__ import annotations

import ipaddress
import re
import socket
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 512 * 1024
TIMEOUT_SECONDS = 10.0
ALLOW_LOOPBACK = True  # 自托管场景下允许预览本机站点；其余内网地址一律拒绝

_TAG_RE = re.compile(r"(?s)<[^>]+>")
_SCRIPT_RE = re.compile(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>")
_TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_META_DESC_RE = re.compile(
    r"(?is)<meta\s+[^>]*name=[\"']description[\"'][^>]*content=[\"']([^\"']*)[\"']"
)
_META_DESC_RE_ALT = re.compile(
    r"(?is)<meta\s+[^>]*content=[\"']([^\"']*)[\"'][^>]*name=[\"']description[\"']"
)
_CANONICAL_RE = re.compile(r"(?is)<link\s+[^>]*rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']*)[\"']")
_OG_TITLE_RE = re.compile(
    r"(?is)<meta\s+[^>]*property=[\"']og:title[\"'][^>]*content=[\"']([^\"']*)[\"']"
)
_H1_RE = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
_H2_RE = re.compile(r"(?is)<h2[^>]*>.*?</h2>")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


class CrawlError(ValueError):
    """抓取被安全策略拒绝，或目标不可达。"""


def build_target_url(site_url: str, slug: str = "", path: str = "") -> str:
    """由站点 URL 与页面 slug / 相对路径拼出待抓取地址。"""
    base = (site_url or "").strip()
    if not base:
        raise CrawlError("站点未配置 URL，无法预览")
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    base = base.rstrip("/") + "/"
    suffix = (path or "").strip()
    if not suffix:
        suffix = (slug or "").strip().strip("/")
    return urljoin(base, suffix) if suffix else base


def _assert_same_host(url: str, site_url: str) -> None:
    target = urlparse(url)
    origin = urlparse(site_url if site_url.startswith(("http://", "https://")) else "http://" + site_url)
    if target.scheme not in ("http", "https"):
        raise CrawlError("仅支持 http / https 地址")
    if not target.hostname:
        raise CrawlError("目标地址缺少主机名")
    if target.hostname != origin.hostname:
        raise CrawlError(f"仅允许抓取本站同域地址（站点域名: {origin.hostname}）")
    _assert_public_host(target.hostname)


def _assert_public_host(host: str) -> None:
    candidates: list[str] = []
    try:
        ipaddress.ip_address(host)
        candidates.append(host)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise CrawlError(f"域名解析失败: {host}") from exc
        candidates = [info[4][0] for info in infos]
    for raw in candidates:
        try:
            ip = ipaddress.ip_address(raw.split("%")[0])
        except ValueError:
            continue
        if ip.is_loopback:
            if ALLOW_LOOPBACK:
                continue
            raise CrawlError("出于安全考虑，禁止抓取本机回环地址")
        if ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise CrawlError(f"出于安全考虑，禁止抓取内网 / 保留地址: {raw}")


def _decode(raw: bytes, content_type: str) -> str:
    charset = ""
    match = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if match:
        charset = match.group(1)
    if not charset:
        sniff = re.search(rb"charset=[\"']?([\w\-]+)", raw[:4096])
        if sniff:
            charset = sniff.group(1).decode("ascii", "ignore")
    for enc in [charset, "utf-8", "gb18030"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="ignore")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()


def _first(pattern: re.Pattern[str], html: str) -> str:
    match = pattern.search(html)
    return _normalize(match.group(1)) if match else ""


def _diagnose(
    title: str,
    desc: str,
    h1: list[str],
    canonical: str,
    og_title: str,
    word_count: int,
    status_code: int,
    scheme: str,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    def add(level: str, item: str, message: str) -> None:
        items.append({"level": level, "item": item, "message": message})

    if status_code >= 400:
        add("error", "HTTP 状态", f"返回 {status_code}，页面不可正常访问")
    elif status_code >= 300:
        add("warn", "HTTP 状态", f"返回 {status_code}，存在重定向，建议核对地址")

    if not title:
        add("error", "title", "缺少 title 标签")
    elif len(title) < 10:
        add("warn", "title", f"长度偏短（{len(title)} 字），建议 10-60 字")
    elif len(title) > 60:
        add("warn", "title", f"长度偏长（{len(title)} 字），搜索结果可能被截断")
    else:
        add("ok", "title", f"长度合适（{len(title)} 字）")

    if not desc:
        add("error", "meta description", "缺少 meta description")
    elif len(desc) < 50:
        add("warn", "meta description", f"长度偏短（{len(desc)} 字），建议 50-160 字")
    elif len(desc) > 160:
        add("warn", "meta description", f"长度偏长（{len(desc)} 字），建议控制在 160 字内")
    else:
        add("ok", "meta description", f"长度合适（{len(desc)} 字）")

    if not h1:
        add("warn", "H1", "缺少 H1 标题")
    elif len(h1) > 1:
        add("warn", "H1", f"存在 {len(h1)} 个 H1，建议每页仅保留 1 个")
    else:
        add("ok", "H1", "H1 唯一")

    if canonical:
        add("ok", "canonical", "已声明")
    else:
        add("warn", "canonical", "缺少 canonical 声明")

    if og_title:
        add("ok", "og:title", "已声明")
    else:
        add("warn", "og:title", "缺少 Open Graph 标题")

    if word_count < 300:
        add("warn", "正文字数", f"仅 {word_count} 字，内容偏薄，建议 ≥300 字")
    else:
        add("ok", "正文字数", f"{word_count} 字")

    if scheme != "https":
        add("warn", "协议", "当前为 http，建议启用 https")
    return items


def crawl(
    url: str,
    site_url: str,
    max_bytes: int = MAX_BYTES,
    timeout: float = TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """抓取同域页面并返回结构化体检结果。"""
    _assert_same_host(url, site_url)
    started = time.perf_counter()
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": "OpsCompass-Crawler/0.5 (+builtin-browser)"},
        ) as client:
            with client.stream("GET", url) as resp:
                raw = b""
                for chunk in resp.iter_bytes():
                    raw += chunk
                    if len(raw) >= max_bytes:
                        raw = raw[:max_bytes]
                        break
                status_code = resp.status_code
                final_url = str(resp.url)
                headers = {k.lower(): v for k, v in resp.headers.items()}
    except httpx.HTTPError as exc:
        raise CrawlError(f"抓取失败: {exc.__class__.__name__}: {exc}") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    content_type = headers.get("content-type", "")
    html = _decode(raw, content_type)

    title = _first(_TITLE_RE, html)
    desc = _first(_META_DESC_RE, html) or _first(_META_DESC_RE_ALT, html)
    h1 = [_normalize(x) for x in _H1_RE.findall(html) if _normalize(x)]
    h2_count = len(_H2_RE.findall(html))
    canonical = _first(_CANONICAL_RE, html)
    og_title = _first(_OG_TITLE_RE, html)
    text = _normalize(_SCRIPT_RE.sub(" ", html))
    word_count = len(_CJK_RE.findall(text)) + len(_WORD_RE.findall(text))
    scheme = urlparse(final_url).scheme

    return {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "content_type": content_type,
        "bytes": len(raw),
        "title": title,
        "meta_description": desc,
        "h1": h1,
        "h2_count": h2_count,
        "word_count": word_count,
        "canonical": canonical,
        "og_title": og_title,
        "text_preview": text[:300],
        "diagnostics": _diagnose(
            title, desc, h1, canonical, og_title, word_count, status_code, scheme
        ),
    }
