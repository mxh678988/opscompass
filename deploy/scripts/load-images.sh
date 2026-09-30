#!/usr/bin/env bash
# ==============================================================
# 运营智脑 OpsCompass · 离线镜像载入脚本（服务器执行）
# 版权：BY LAOMENG 网络工作室
# --------------------------------------------------------------
# 作用：校验离线镜像包 SHA256（若同目录存在 .sha256 文件）后载入本地镜像库。
# 用法：
#   bash deploy/scripts/load-images.sh deploy/dist/opscompass-0.10.1-images.tar
#   SKIP_CHECK=1 bash deploy/scripts/load-images.sh <tar>   # 跳过校验（不推荐）
# 退出码：0 成功；1 参数错误；2 文件缺失；3 校验失败；4 载入失败
# ==============================================================
set -euo pipefail

TAR_PATH="${1:-}"
if [[ -z "$TAR_PATH" ]]; then
    echo "用法: bash deploy/scripts/load-images.sh <镜像包 tar 路径>" >&2
    exit 1
fi

if [[ ! -f "$TAR_PATH" ]]; then
    echo "[load] 文件不存在: $TAR_PATH" >&2
    exit 2
fi

# ---------- 1. 校验 SHA256 ----------
SHA_PATH="${TAR_PATH}.sha256"
if [[ "${SKIP_CHECK:-0}" == "1" ]]; then
    echo "[load] 已跳过 SHA256 校验（SKIP_CHECK=1）"
elif [[ -f "$SHA_PATH" ]]; then
    echo "[load] 校验 SHA256 ..."
    EXPECTED="$(awk '{print $1}' "$SHA_PATH" | tr 'A-Z' 'a-z')"
    if command -v sha256sum >/dev/null 2>&1; then
        ACTUAL="$(sha256sum "$TAR_PATH" | awk '{print $1}')"
    else
        ACTUAL="$(shasum -a 256 "$TAR_PATH" | awk '{print $1}')"
    fi
    if [[ "$EXPECTED" != "$ACTUAL" ]]; then
        echo "[load] SHA256 校验失败！" >&2
        echo "  期望: $EXPECTED" >&2
        echo "  实际: $ACTUAL" >&2
        echo "  镜像包可能损坏或被篡改，已中止载入。" >&2
        exit 3
    fi
    echo "[load] SHA256 校验通过: $ACTUAL"
else
    echo "[load] 警告：未找到 $SHA_PATH，跳过校验（建议随包分发 .sha256 文件）" >&2
fi

# ---------- 2. 载入镜像 ----------
SIZE_MB=$(( $(stat -c%s "$TAR_PATH" 2>/dev/null || stat -f%z "$TAR_PATH") / 1024 / 1024 ))
echo "[load] 正在载入镜像（${SIZE_MB} MB）..."
if ! docker load -i "$TAR_PATH"; then
    echo "[load] docker load 失败" >&2
    exit 4
fi

# ---------- 3. 结果确认 ----------
echo "[load] 当前 OpsCompass 相关镜像："
docker images --format '{{.Repository}}:{{.Tag}}  {{.ID}}  {{.Size}}' | grep -E '^opscompass-' || \
    echo "  （未发现 opscompass- 前缀镜像，请检查打包内容）"

echo ""
echo "[load] 下一步："
echo "  docker compose -f docker-compose.prod.yml up -d"
echo "  curl -fsS http://127.0.0.1/health   # 健康检查"
